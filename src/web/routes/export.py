"""导出路由。

当前仅支持：
- HTML 群聊年度总结（模板：group_year_summary）

导出数据来源：群体分析缓存（exports/.analysis_cache/<id>.pkl）。
"""

from __future__ import annotations

import logging
import pickle
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from uuid import uuid4

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
		ts = datetime.now().strftime('%Y%m%d_%H%M%S')
		ascii_name = f"group_year_summary_{ts}.html"
		utf8_name = f"群聊年度总结_{ts}.html"
		# WSGI 头必须是 latin-1 可编码字符串；因此提供 ASCII filename，同时用 RFC5987 的 filename* 提供 UTF-8 百分号编码。
		resp.headers['Content-Disposition'] = (
			f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{quote(utf8_name)}'
		)
		return resp

	except Exception as e:
		logger.exception('Error exporting report')
		return _json_error(f'导出失败：{e}', 500)


# ==================================================
# Network PNG export (server-side stitching)
# ==================================================


def export_network_png_start():
	"""Start a stitched network PNG export job.

	POST /api/export/network/png/start
	JSON: { file?: str, scale?: int, nx: int, ny: int, tile_width: int, tile_height: int }
	Returns: { success: true, job_id: str }
	"""
	try:
		payload = request.get_json(silent=True) or {}
		nx = int(payload.get('nx') or 0)
		ny = int(payload.get('ny') or 0)
		tw = int(payload.get('tile_width') or 0)
		th = int(payload.get('tile_height') or 0)
		scale = int(payload.get('scale') or 1)

		if nx <= 0 or ny <= 0 or tw <= 0 or th <= 0:
			return _json_error('缺少或非法的 nx/ny/tile_width/tile_height', 400)
		if scale <= 0:
			scale = 1

		job_id = uuid4().hex
		tmp_dir = Path('exports') / '.tmp_network_export' / job_id
		tmp_dir.mkdir(parents=True, exist_ok=True)

		meta = {
			'created_at': datetime.now().isoformat(),
			'file': (payload.get('file') or ''),
			'scale': scale,
			'nx': nx,
			'ny': ny,
			'tile_width': tw,
			'tile_height': th,
		}
		(tmp_dir / 'meta.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')

		return jsonify({'success': True, 'job_id': job_id})
	except Exception as e:
		logger.exception('export_network_png_start failed')
		return _json_error(f'启动导出失败：{e}', 500)


def export_network_png_tile():
	"""Upload one tile image for a network PNG export job.

	POST /api/export/network/png/tile
	multipart/form-data:
	- job_id: str
	- row: int
	- col: int
	- tile_width: int (canvas actual width)
	- tile_height: int (canvas actual height)
	- tile: file (png)
	"""
	try:
		job_id = (request.form.get('job_id') or '').strip()
		if not job_id:
			return _json_error('缺少 job_id', 400)

		row = int(request.form.get('row') or -1)
		col = int(request.form.get('col') or -1)
		if row < 0 or col < 0:
			return _json_error('缺少或非法的 row/col', 400)

		f = request.files.get('tile')
		if not f:
			return _json_error('缺少 tile 文件', 400)

		tmp_dir = Path('exports') / '.tmp_network_export' / job_id
		if not tmp_dir.exists():
			return _json_error('job_id 不存在或已过期', 404)

		# 保存 tile 图片
		out_path = tmp_dir / f"tile_r{row:04d}_c{col:04d}.png"
		f.save(out_path)

		# 保存该 tile 的实际宽高元数据（用于精确拼接，处理高 DPI 等情况）
		try:
			tw = int(request.form.get('tile_width') or 0)
			th = int(request.form.get('tile_height') or 0)
			if tw > 0 and th > 0:
				meta_path = tmp_dir / f"tile_r{row:04d}_c{col:04d}.json"
				meta_path.write_text(
					json.dumps({'width': tw, 'height': th}, ensure_ascii=False),
					encoding='utf-8'
				)
		except Exception as e:
			logger.warning('Failed to save tile metadata: %s', e)

		return jsonify({'success': True})
	except Exception as e:
		logger.exception('export_network_png_tile failed')
		return _json_error(f'上传分块失败：{e}', 500)


def export_network_png_finish():
	"""Finish stitching all tiles into a single big PNG.

	POST /api/export/network/png/finish
	JSON: { job_id: str, nx: int, ny: int, tile_width: int, tile_height: int, scale?: int }
	Returns: { success: true, export_path: str }
	"""
	try:
		payload = request.get_json(silent=True) or {}
		job_id = (payload.get('job_id') or '').strip()
		if not job_id:
			return _json_error('缺少 job_id', 400)

		nx = int(payload.get('nx') or 0)
		ny = int(payload.get('ny') or 0)
		tw = int(payload.get('tile_width') or 0)
		th = int(payload.get('tile_height') or 0)
		scale = int(payload.get('scale') or 1)
		if nx <= 0 or ny <= 0 or tw <= 0 or th <= 0:
			return _json_error('缺少或非法的 nx/ny/tile_width/tile_height', 400)
		if scale <= 0:
			scale = 1

		tmp_dir = Path('exports') / '.tmp_network_export' / job_id
		if not tmp_dir.exists():
			return _json_error('job_id 不存在或已过期', 404)

		try:
			from PIL import Image
			from PIL import ImageFile
			ImageFile.LOAD_TRUNCATED_IMAGES = True
			# 允许大图（拼接输出可能非常大）
			try:
				Image.MAX_IMAGE_PIXELS = None
			except Exception:
				pass
		except Exception as e:
			return _json_error(f'缺少 Pillow 依赖（PIL）：{e}', 500)

		out_w = int(tw * nx)
		out_h = int(th * ny)

		# 极端情况下 PNG 可能无法创建（内存/尺寸限制）。这里不做过小的“安全上限”，但仍做基本保护。
		if out_w <= 0 or out_h <= 0:
			return _json_error('输出尺寸非法', 400)

		logger.info('Stitching network PNG: job=%s tiles=%sx%s out=%sx%s', job_id, nx, ny, out_w, out_h)

		canvas = Image.new('RGBA', (out_w, out_h), (0, 0, 0, 0))
		missing = []
		for r in range(ny):
			for c in range(nx):
				p = tmp_dir / f"tile_r{r:04d}_c{c:04d}.png"
				if not p.exists():
					missing.append((r, c))
					continue
				img = Image.open(p)
				if img.mode != 'RGBA':
					img = img.convert('RGBA')
				canvas.paste(img, (c * tw, r * th))
				try:
					img.close()
				except Exception:
					pass

		if missing:
			return _json_error(f'缺少分块：{missing[:10]} (共 {len(missing)} 个)', 400)

		export_dir = Path('exports')
		export_dir.mkdir(parents=True, exist_ok=True)
		ts = datetime.now().strftime('%Y%m%d_%H%M%S')
		out_path = export_dir / f"network_graph_{ts}_{scale}x.png"
		canvas.save(out_path, format='PNG', optimize=False)
		try:
			canvas.close()
		except Exception:
			pass

		# 清理临时目录（可选：保留调试时可注释）
		try:
			for f in tmp_dir.glob('tile_*.png'):
				f.unlink(missing_ok=True)
			(tmp_dir / 'meta.json').unlink(missing_ok=True)
			tmp_dir.rmdir()
		except Exception:
			# ignore cleanup failures
			pass

		return jsonify({
			'success': True,
			'export_path': str(out_path).replace('\\', '/'),
			'width': out_w,
			'height': out_h,
			'nx': nx,
			'ny': ny,
		})

	except Exception as e:
		logger.exception('export_network_png_finish failed')
		return _json_error(f'拼接导出失败：{e}', 500)

