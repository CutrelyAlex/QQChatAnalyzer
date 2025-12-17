"""导出路由。

当前仅支持：
- HTML 群聊年度总结（模板：group_year_summary）

导出数据来源：群体分析缓存（exports/.analysis_cache/<id>.pkl）。
"""

from __future__ import annotations

import logging
import pickle
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import jsonify, make_response, render_template, request

from src.web.services.conversation_loader import load_conversation_and_messages


logger = logging.getLogger(__name__)


def _json_error(message: str, status: int = 400):
	return jsonify({'success': False, 'error': message}), status


def _normalize_word_list(words: Any) -> List[str]:
	if not isinstance(words, list):
		return []
	out: List[str] = []
	for w in words:
		s = ('' if w is None else str(w)).strip()
		if not s:
			continue
		out.append(s)
	return out


def _extract_group_stats(cache_data: Dict[str, Any]) -> Dict[str, Any]:
	"""兼容两种缓存 schema：

	- data = { group_stats: {...} }
	- data = {...}  (直接就是 group_stats)
	"""

	payload = cache_data.get('data') or {}
	if isinstance(payload, dict) and isinstance(payload.get('group_stats'), dict):
		return payload.get('group_stats') or {}
	if isinstance(payload, dict):
		return payload
	return {}


def _word_count_map(group_stats: Dict[str, Any]) -> Dict[str, int]:
	m: Dict[str, int] = {}
	hot_words_raw = group_stats.get('hot_words') or []
	if not isinstance(hot_words_raw, list):
		return m
	for it in hot_words_raw:
		try:
			if isinstance(it, dict):
				w = (it.get('word') or '').strip()
				c = int(it.get('count') or 0)
			elif isinstance(it, (list, tuple)) and len(it) >= 2:
				w = (str(it[0]) or '').strip()
				c = int(it[1] or 0)
			else:
				continue
			if w:
				m[w] = c
		except Exception:
			continue
	return m


def _collect_examples_for_word(messages: List[Dict[str, Any]], word: str, limit: int = 5) -> List[Dict[str, Any]]:
	# messages 是 web/services/conversation_loader.py 输出的 dict 列表
	# 关键字段：time/sender/qq/content
	out: List[Dict[str, Any]] = []
	if not word:
		return out

	for m in messages:
		try:
			content = (m.get('content') or '').strip()
			if not content:
				continue
			if word not in content:
				continue
			out.append({
				'timestamp': m.get('time', ''),
				'sender': m.get('sender', ''),
				'qq': m.get('qq', ''),
				'content': content,
			})
			if len(out) >= limit:
				break
		except Exception:
			continue
	return out


def _top_speakers_from_stats(group_stats: Dict[str, Any], top_n: int = 5) -> List[Dict[str, Any]]:
	mmc = group_stats.get('member_message_count') or {}
	items: List[Dict[str, Any]] = []
	if isinstance(mmc, dict):
		for qq, v in mmc.items():
			if isinstance(v, dict):
				name = (v.get('name') or '').strip()
				count = int(v.get('count') or 0)
			else:
				name = ''
				try:
					count = int(v or 0)
				except Exception:
					count = 0
			items.append({
				'qq': str(qq) if qq is not None else '',
				'name': name or (str(qq) if qq is not None else ''),
				'count': count,
			})
	items.sort(key=lambda x: int(x.get('count') or 0), reverse=True)
	return items[: max(0, int(top_n))]


def _pick_sleepy_titles(group_stats: Dict[str, Any]) -> tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
	"""基于 hourly_top_users 的“近似”夜猫子/早起鸟。

	hourly_top_users: {hour: {qq,name,count}}
	- 夜猫子：优先 0-5 点
	- 早起鸟：优先 6-9 点
	若缺失则返回 None。
	"""

	htu = group_stats.get('hourly_top_users') or {}
	if not isinstance(htu, dict):
		return None, None

	def _best_in_hours(hours: List[int]) -> Optional[Dict[str, Any]]:
		best = None
		best_count = -1
		for h in hours:
			raw = htu.get(str(h)) if str(h) in htu else htu.get(h)
			if not isinstance(raw, dict):
				continue
			try:
				c = int(raw.get('count') or 0)
			except Exception:
				c = 0
			if c > best_count:
				best_count = c
				best = {
					'hour': h,
					'qq': (raw.get('qq') or '').strip(),
					'name': (raw.get('name') or '').strip(),
					'count': c,
				}
		return best

	return _best_in_hours([0, 1, 2, 3, 4, 5]), _best_in_hours([6, 7, 8, 9])


def export_report(format_type: str):
	"""导出报告。

	POST /api/export/<format_type>
	- 仅支持 html
	- payload: { template: 'group_year_summary', cache_id: str, words: [8 words] }
	"""

	try:
		if (format_type or '').lower() != 'html':
			return _json_error('仅支持导出 HTML', 400)

		payload = request.get_json(silent=True) or {}
		template = (payload.get('template') or '').strip()
		if template != 'group_year_summary':
			return _json_error('不支持的导出模板', 400)

		cache_id = (payload.get('cache_id') or '').strip()
		if not cache_id:
			return _json_error('缺少 cache_id', 400)

		selected_words = _normalize_word_list(payload.get('words') or [])
		if len(selected_words) != 8:
			return _json_error('请恰好选择 8 个热词', 400)

		cache_file = Path('exports/.analysis_cache') / f"{cache_id}.pkl"
		if not cache_file.exists():
			return _json_error('缓存不存在', 404)

		with open(cache_file, 'rb') as f:
			cache_data = pickle.load(f)

		if cache_data.get('type') != 'group':
			return _json_error('所选缓存不是群体分析类型', 400)

		filename = cache_data.get('filename')
		if not filename:
			return _json_error('缓存缺少 filename', 500)

		group_stats = _extract_group_stats(cache_data)
		word_to_count = _word_count_map(group_stats)

		# 拉取例句：直接读取原文件的规范化消息
		_conv, messages, _warnings = load_conversation_and_messages(str(filename))

		selected_hotwords: List[Dict[str, Any]] = []
		for w in selected_words:
			selected_hotwords.append({
				'word': w,
				'count': int(word_to_count.get(w, 0) or 0),
				'examples': _collect_examples_for_word(messages, w, limit=5),
			})

		# 4 页：每页 2 个热词
		hotword_pages: List[Dict[str, Any]] = []
		for i in range(4):
			hotword_pages.append({
				'index': i + 1,
				'words': selected_hotwords[i * 2 : i * 2 + 2],
			})

		top_speakers = _top_speakers_from_stats(group_stats, top_n=5)
		top_night_owl, top_early_bird = _pick_sleepy_titles(group_stats)
		top_mention_sender = group_stats.get('top_mention_sender')
		if not isinstance(top_mention_sender, dict):
			top_mention_sender = None

		html = render_template(
			'exports/group_year_summary.html',
			filename=filename,
			generated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
			group_stats=group_stats,
			hotword_pages=hotword_pages,
			top_speakers=top_speakers,
			top_night_owl=top_night_owl,
			top_early_bird=top_early_bird,
			top_mention_sender=top_mention_sender,
		)

		resp = make_response(html)
		resp.headers['Content-Type'] = 'text/html; charset=utf-8'
		dl_name = f"群聊年度总结_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
		resp.headers['Content-Disposition'] = f"attachment; filename*=UTF-8''{dl_name}"
		return resp

	except Exception as e:
		logger.exception('Error exporting report')
		return _json_error(f'导出失败：{e}', 500)

