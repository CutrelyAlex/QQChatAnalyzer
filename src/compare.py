"""对比工具（US3）。

目标：
- 让前端能选择两段聊天（文件级别）并排对比关键指标

说明：
- compare 只依赖分析器输出 dict（GroupStats/NetworkStats.to_dict）以及 Conversation 元信息
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


def _safe_float(x: Any, default: float = 0.0) -> float:
	try:
		if x is None:
			return default
		return float(x)
	except Exception:
		return default


def _safe_int(x: Any, default: int = 0) -> int:
	try:
		if x is None:
			return default
		return int(x)
	except Exception:
		return default


def _delta(a: Any, b: Any) -> Dict[str, Any]:
	"""返回 {left,right,delta,deltaPct}（deltaPct 以 left 为基准）。"""

	left = _safe_float(a)
	right = _safe_float(b)
	d = right - left
	pct = None
	if left != 0:
		pct = d / left
	return {
		"left": a,
		"right": b,
		"delta": d,
		"deltaPct": pct,
	}


@dataclass(frozen=True)
class CompareSnapshot:
	filename: str
	conversation: Dict[str, Any]
	group: Dict[str, Any]
	network: Optional[Dict[str, Any]]

	def to_dict(self) -> Dict[str, Any]:
		return {
			"filename": self.filename,
			"conversation": self.conversation,
			"group": self.group,
			"network": self.network or {},
		}


def build_snapshot(
	*,
	filename: str,
	conversation: Any,
	group_stats: Dict[str, Any],
	network_stats: Optional[Dict[str, Any]] = None,
) -> CompareSnapshot:
	"""把 Conversation + 分析器输出压缩成用于 UI 对比的稳定快照。"""

	conv_dict = {
		"conversationId": getattr(conversation, "conversation_id", None),
		"type": getattr(conversation, "type", None),
		"title": getattr(conversation, "title", None),
		"participants": _safe_int(len(getattr(conversation, "participants", []) or [])),
		"messageCountRaw": _safe_int(getattr(conversation, "message_count_raw", 0)),
	}

	# group_stats：抽取 UI 需要的少量字段
	group_compact = {
		"total_messages": _safe_int(group_stats.get("total_messages")),
		"daily_average": _safe_float(group_stats.get("daily_average")),
		"peak_hours": group_stats.get("peak_hours", []) or [],

		"text_ratio": _safe_float(group_stats.get("text_ratio")),
		"image_ratio": _safe_float(group_stats.get("image_ratio")),
		"emoji_ratio": _safe_float(group_stats.get("emoji_ratio")),
		"link_ratio": _safe_float(group_stats.get("link_ratio")),
		"forward_ratio": _safe_float(group_stats.get("forward_ratio")),
		"system_messages": _safe_int(group_stats.get("system_messages")),
		"recalled_messages": _safe_int(group_stats.get("recalled_messages")),
		"mention_messages": _safe_int(group_stats.get("mention_messages")),
		"reply_messages": _safe_int(group_stats.get("reply_messages")),
		"media_messages": _safe_int(group_stats.get("media_messages")),
		"media_breakdown": group_stats.get("media_breakdown", {}) if isinstance(group_stats.get("media_breakdown", {}), dict) else {},
	}

	net_compact = None
	if network_stats:
		net_compact = {
			"total_nodes": _safe_int(network_stats.get("total_nodes")),
			"total_edges": _safe_int(network_stats.get("total_edges")),
			"density": _safe_float(network_stats.get("density")),
			"average_clustering": _safe_float(network_stats.get("average_clustering")),
		}

	return CompareSnapshot(filename=filename, conversation=conv_dict, group=group_compact, network=net_compact)


def diff_snapshots(left: CompareSnapshot, right: CompareSnapshot) -> Dict[str, Any]:
	"""生成可渲染的差异结构（主要关注数值字段）。"""

	l = left.to_dict()
	r = right.to_dict()

	fields = {
		"participants": (l["conversation"].get("participants"), r["conversation"].get("participants")),
		"messageCountRaw": (l["conversation"].get("messageCountRaw"), r["conversation"].get("messageCountRaw")),
		"total_messages": (l["group"].get("total_messages"), r["group"].get("total_messages")),
		"daily_average": (l["group"].get("daily_average"), r["group"].get("daily_average")),
		"system_messages": (l["group"].get("system_messages"), r["group"].get("system_messages")),
		"recalled_messages": (l["group"].get("recalled_messages"), r["group"].get("recalled_messages")),
		"mention_messages": (l["group"].get("mention_messages"), r["group"].get("mention_messages")),
		"reply_messages": (l["group"].get("reply_messages"), r["group"].get("reply_messages")),
		"media_messages": (l["group"].get("media_messages"), r["group"].get("media_messages")),
	}

	if left.network and right.network:
		fields.update(
			{
				"total_nodes": (l["network"].get("total_nodes"), r["network"].get("total_nodes")),
				"total_edges": (l["network"].get("total_edges"), r["network"].get("total_edges")),
				"density": (l["network"].get("density"), r["network"].get("density")),
				"average_clustering": (l["network"].get("average_clustering"), r["network"].get("average_clustering")),
			}
		)

	diff = {k: _delta(v[0], v[1]) for k, v in fields.items()}

	# media_breakdown：单独按 key 合并
	mb_left = l["group"].get("media_breakdown") or {}
	mb_right = r["group"].get("media_breakdown") or {}
	mb_keys = sorted(set(mb_left.keys()) | set(mb_right.keys()))
	diff_media = {k: _delta(mb_left.get(k, 0), mb_right.get(k, 0)) for k in mb_keys}

	return {
		"fields": diff,
		"media_breakdown": diff_media,
	}