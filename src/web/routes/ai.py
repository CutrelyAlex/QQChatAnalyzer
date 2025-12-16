import json
import logging
from datetime import datetime
from pathlib import Path

from flask import jsonify, request

from src.config import Config
from src.web.services.ai_context import prepare_ai_summary_context
from src.web.services.conversation_loader import load_conversation_and_messages


logger = logging.getLogger(__name__)
def ai_status():
    """T044: 检查AI服务状态"""
    try:
        api_key = Config.OPENAI_API_KEY
        is_available = bool(api_key)

        return jsonify({
            'success': True,
            'available': is_available,
            'model': Config.OPENAI_MODEL,
            'apiBase': Config.OPENAI_API_BASE or 'https://api.openai.com/v1',
            'message': 'AI服务可用' if is_available else 'AI服务未配置，请设置 OPENAI_API_KEY 环境变量'
        })
    except Exception as e:
        logger.error(f"Error checking AI status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

def test_ai_connection():
    """测试AI连接配置"""
    try:
        data = request.get_json()
        api_base = data.get('api_base', '')
        api_key = data.get('api_key', '')
        model = data.get('model', 'gpt-4o-mini')
        timeout = data.get('timeout', 30)

        if not api_key or not api_base:
            return jsonify({'success': False, 'error': '请提供API密钥和基础URL'}), 400

        try:
            from openai import OpenAI

            client = OpenAI(api_key=api_key, base_url=api_base)
            client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5,
                timeout=timeout,
            )

            return jsonify({'success': True, 'message': '连接成功', 'model': model, 'base_url': api_base})
        except Exception as e:
            return jsonify({'success': False, 'error': f'连接失败: {str(e)}'}), 400
    except Exception as e:
        logger.error(f"Error testing AI connection: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

def token_estimate():
    """T045: Token预估API"""
    try:
        data = request.get_json()
        filename = data.get('filename')
        max_tokens = data.get('max_tokens', Config.DEFAULT_MAX_TOKENS)

        if not filename:
            return jsonify({'success': False, 'error': '未指定文件'}), 400

        try:
            _conv, messages, _warnings = load_conversation_and_messages(filename)
        except FileNotFoundError:
            return jsonify({'success': False, 'error': '文件不存在'}), 404

        from src.data_pruner import DataPruner

        pruner = DataPruner(max_tokens)
        pruner.load_messages(messages)
        estimate = pruner.estimate_tokens()
        strategy = pruner.calculate_pruning_strategy()

        return jsonify({'success': True, 'estimate': estimate, 'pruning_strategy': strategy})
    except Exception as e:
        logger.error(f"Error estimating tokens: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

def generate_summary():
    """T056: 生成AI总结 - 支持从缓存数据或实时分析"""
    try:
        data = request.get_json() or {}

        export_prompt_only = bool(data.get('export_prompt_only') or data.get('exportPromptOnly'))

        ctx = prepare_ai_summary_context(data)

        from src.ai_summarizer import AISummarizer

        summarizer = AISummarizer(
            model=Config.OPENAI_MODEL,
            max_tokens=ctx['max_tokens'],
            api_key=Config.OPENAI_API_KEY,
            base_url=Config.OPENAI_API_BASE,
            context_budget=ctx['context_budget'],
            timeout=int(Config.OPENAI_REQUEST_TIMEOUT),
            temperature=ctx['temperature'],
            top_p=ctx['top_p'],
        )

        prompts = summarizer.build_prompts(
            summary_type=ctx['summary_type'],
            stats=ctx['stats'],
            group_stats=ctx['group_stats'],
            network_stats=ctx['network_stats'],
            messages=ctx['messages'],
            qq=ctx['qq'],
            chat_sample=ctx['chat_sample'],
        )

        # 仅导出 prompt：用于 e2e 流程验证（不触发外部请求，不依赖 OPENAI_API_KEY）
        if export_prompt_only:
            export_dir = Path('exports') / 'ai_prompts'
            export_dir.mkdir(parents=True, exist_ok=True)

            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            safe_name = str(ctx.get('filename') or 'unknown').replace('\\', '_').replace('/', '_').replace(':', '_')
            out_path = export_dir / f"ai_prompt_{prompts.get('normalized_type','summary')}_{safe_name}_{ts}.json"

            payload = {
                'exported_at': datetime.now().isoformat(),
                'filename': ctx.get('filename'),
                'summary_type': prompts.get('normalized_type') or ctx.get('summary_type'),
                'model': summarizer.model,
                'temperature': summarizer.temperature,
                'top_p': summarizer.top_p,
                'max_tokens': ctx.get('max_tokens'),
                'context_budget': ctx.get('context_budget'),
                'messages': [
                    {"role": "system", "content": prompts.get('system_prompt', '')},
                    {"role": "user", "content": prompts.get('user_prompt', '')},
                ],
            }

            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)

            return jsonify({
                'success': True,
                'export_prompt_only': True,
                'export_path': str(out_path).replace('\\', '/'),
                'normalized_type': payload['summary_type'],
                'model': payload['model'],
            })

        # 非导出模式：需要真实 OpenAI 调用
        if not Config.OPENAI_API_KEY or (not summarizer.is_available()):
            return jsonify({'success': False, 'error': 'AI服务未配置，请设置 OPENAI_API_KEY 环境变量'}), 503

        logger.info(
            f"Generating {prompts['normalized_type']} AI summary for {ctx.get('filename')} "
            f"(max_tokens={ctx['max_tokens']}, context_budget={ctx['context_budget']}, "
            f"temperature={summarizer.temperature}, top_p={summarizer.top_p})"
        )

        response = summarizer.client.chat.completions.create(
            model=summarizer.model,
            messages=[
                {"role": "system", "content": prompts['system_prompt']},
                {"role": "user", "content": prompts['user_prompt']},
            ],
            max_tokens=summarizer.max_tokens,
            temperature=summarizer.temperature,
            top_p=summarizer.top_p,
        )

        summary = response.choices[0].message.content if response.choices else ''
        tokens_used = response.usage.total_tokens if getattr(response, 'usage', None) else 0

        return jsonify({
            'success': True,
            'summary': summary or '',
            'tokens_used': tokens_used,
            'model': summarizer.model,
            'temperature': summarizer.temperature,
            'top_p': summarizer.top_p,
            'error': ''
        })

    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except FileNotFoundError as e:
        return jsonify({'success': False, 'error': str(e)}), 404
    except PermissionError as e:
        return jsonify({'success': False, 'error': str(e)}), 403
    except Exception as e:
        logger.error(f"Error generating summary: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

def generate_summary_stream():
    """T056b: 流式生成AI总结 - 支持从缓存数据或实时分析"""
    from flask import Response, stream_with_context

    try:
        data = request.get_json() or {}
        if not Config.OPENAI_API_KEY:
            return jsonify({'success': False, 'error': 'AI服务未配置'}), 503

        ctx = prepare_ai_summary_context(data)
        from src.ai_summarizer import AISummarizer

        summarizer = AISummarizer(
            model=Config.OPENAI_MODEL,
            max_tokens=ctx['max_tokens'],
            api_key=Config.OPENAI_API_KEY,
            base_url=Config.OPENAI_API_BASE,
            context_budget=ctx['context_budget'],
            timeout=int(Config.OPENAI_REQUEST_TIMEOUT),
            temperature=ctx['temperature'],
            top_p=ctx['top_p'],
        )

        if not summarizer.is_available():
            return jsonify({'success': False, 'error': 'AI服务未配置'}), 503

        prompts = summarizer.build_prompts(
            summary_type=ctx['summary_type'],
            stats=ctx['stats'],
            group_stats=ctx['group_stats'],
            network_stats=ctx['network_stats'],
            messages=ctx['messages'],
            qq=ctx['qq'],
            chat_sample=ctx['chat_sample'],
        )

        def generate():
            try:
                yield f"data: {json.dumps({'type': 'start', 'model': summarizer.model, 'temperature': summarizer.temperature, 'top_p': summarizer.top_p})}\n\n"

                stream = summarizer.client.chat.completions.create(
                    model=summarizer.model,
                    messages=[
                        {"role": "system", "content": prompts['system_prompt']},
                        {"role": "user", "content": prompts['user_prompt']},
                    ],
                    max_tokens=summarizer.max_tokens,
                    temperature=summarizer.temperature,
                    top_p=summarizer.top_p,
                    stream=True,
                )

                total_content = ""
                for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        total_content += content
                        yield f"data: {json.dumps({'type': 'content', 'content': content})}\n\n"

                yield f"data: {json.dumps({'type': 'done', 'total_length': len(total_content)})}\n\n"
            except Exception as e:
                logger.error(f"Stream error: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

        return Response(
            stream_with_context(generate()),
            mimetype='text/event-stream',
            headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
        )

    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except FileNotFoundError as e:
        return jsonify({'success': False, 'error': str(e)}), 404
    except PermissionError as e:
        return jsonify({'success': False, 'error': str(e)}), 403
    except Exception as e:
        logger.error(f"Error in stream setup: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
