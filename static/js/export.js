/**
 * QQ聊天记录分析系统 - 导出模块
 * 负责年度总结导出配置与 HTML 导出
 */

const exportYearSummary = {
  cacheList: [],
  selectedCache: null,
  hotWords: [],
  selectedWords: new Set(),
};

function _getExportTemplate() {
  return "group_year_summary";
}

function _setExportYearSummaryVisible(visible) {
  const box = document.getElementById("export-year-summary-config");
  if (box) box.style.display = visible ? "block" : "none";
}

function _renderExportYearHotwords() {
  const container = document.getElementById("export-year-hotwords");
  if (!container) return;

  if (!exportYearSummary.selectedCache) {
    container.innerHTML =
      '<div style="color: #999; grid-column: 1 / -1;">请先选择群体分析缓存</div>';
    return;
  }

  if (!exportYearSummary.hotWords.length) {
    container.innerHTML =
      '<div style="color: #999; grid-column: 1 / -1;">该缓存未包含热词数据（hot_words）</div>';
    return;
  }

  container.innerHTML = exportYearSummary.hotWords
    .map((it, idx) => {
      const word = (it?.word ?? "").toString();
      const count = Number(it?.count ?? 0);
      const checked = exportYearSummary.selectedWords.has(word)
        ? "checked"
        : "";
      const id = `export-hotword-${idx}`;
      return `
                <label for="${id}" class="checkbox-item" style="display:flex; align-items:center; gap:8px; padding:8px 10px; border:1px solid #eee; border-radius:10px; background:#fff;">
                    <input id="${id}" type="checkbox" data-word="${escapeHtml(word)}" ${checked}>
                    <span style="flex:1; min-width:0;">${escapeHtml(word)}</span>
                    <small style="color:#999; font-variant-numeric: tabular-nums;">${Number.isFinite(count) ? count : 0}</small>
                </label>
            `;
    })
    .join("");

  container
    .querySelectorAll('input[type="checkbox"][data-word]')
    .forEach((cb) => {
      cb.addEventListener("change", (e) => {
        const w = (e.target?.dataset?.word || "").toString();
        if (!w) return;
        const want = !!e.target.checked;
        if (want) {
          if (exportYearSummary.selectedWords.size >= 8) {
            e.target.checked = false;
            showStatusMessage("error", "最多只能选择 8 个热词");
            return;
          }
          exportYearSummary.selectedWords.add(w);
        } else {
          exportYearSummary.selectedWords.delete(w);
        }
        _updateExportYearSelectedCount();
        _updateExportButtonState();
      });
    });
}

function _updateExportYearSelectedCount() {
  const el = document.getElementById("export-year-selected-count");
  if (!el) return;
  el.textContent = `已选择 ${exportYearSummary.selectedWords.size} / 8`;
}

function _updateExportButtonState() {
  const btn = document.getElementById("export-btn");
  if (!btn) return;

  const ok =
    !!exportYearSummary.selectedCache &&
    exportYearSummary.selectedWords.size === 8;
  btn.disabled = !ok;
  btn.title = ok ? "" : "请选择群体分析缓存并勾选 8 个热词";
}

function _setExportBusy(isBusy, message) {
  const btn = document.getElementById("export-btn");
  const status = document.getElementById("export-status");

  if (btn) {
    if (!btn.dataset.defaultText) {
      btn.dataset.defaultText = (btn.textContent || "").toString();
    }

    if (isBusy) {
      btn.disabled = true;
      btn.classList.add("is-loading");
      btn.textContent = "⏳ 正在导出...";
      btn.title = "正在导出，请稍候...";
    } else {
      btn.classList.remove("is-loading");
      btn.textContent = btn.dataset.defaultText || "📥 导出年度总结（HTML）";
      _updateExportButtonState();
    }
  }

  if (status) {
    const msg = (message || "").toString();
    status.textContent = msg;
    status.className = "status-message" + (isBusy ? " info" : "");
    status.style.display = msg ? "block" : "none";
  }
}

async function _loadGroupCacheList() {
  const sel = document.getElementById("export-group-cache");
  if (!sel) return;

  sel.innerHTML = '<option value="">-- 加载中... --</option>';

  try {
    const resp = await fetch(`${API_BASE}/analysis/cache/list`);
    const data = await resp.json();
    if (!data.success) {
      sel.innerHTML = '<option value="">-- 加载失败 --</option>';
      return;
    }

    exportYearSummary.cacheList = (data.cache_list || []).filter(
      (x) => x?.type === "group",
    );
    sel.innerHTML = '<option value="">-- 请选择群体分析缓存 --</option>';
    exportYearSummary.cacheList.forEach((c) => {
      const opt = document.createElement("option");
      opt.value = c.id;
      opt.textContent = c.display_name || `${c.filename || "未知文件"} (group)`;
      sel.appendChild(opt);
    });

    if (!exportYearSummary.cacheList.length) {
      const meta = document.getElementById("export-year-cache-meta");
      if (meta)
        meta.textContent =
          "暂无群体分析缓存：请先在「群体分析」页分析并保存分析数据。";
    }
  } catch (e) {
    console.error("[Export] Failed to load cache list:", e);
    sel.innerHTML = '<option value="">-- 加载失败 --</option>';
  }
}

async function _loadGroupCacheDetail(cacheId) {
  const meta = document.getElementById("export-year-cache-meta");
  if (meta) meta.textContent = "";

  exportYearSummary.selectedCache = null;
  exportYearSummary.hotWords = [];
  exportYearSummary.selectedWords = new Set();
  _updateExportYearSelectedCount();

  if (!cacheId) {
    _renderExportYearHotwords();
    _updateExportButtonState();
    return;
  }

  try {
    const resp = await fetch(
      `${API_BASE}/analysis/load/${encodeURIComponent(cacheId)}`,
    );
    const data = await resp.json();
    if (!data.success) {
      showStatusMessage("error", data.error || "加载缓存失败");
      _renderExportYearHotwords();
      _updateExportButtonState();
      return;
    }

    exportYearSummary.selectedCache = {
      id: cacheId,
      type: data.type,
      filename: data.filename,
    };
    const stats =
      data?.data?.group_stats && typeof data.data.group_stats === "object"
        ? data.data.group_stats
        : data?.data && typeof data.data === "object"
          ? data.data
          : null;
    exportYearSummary.hotWords = Array.isArray(stats?.hot_words)
      ? stats.hot_words
      : [];

    if (meta) {
      meta.textContent = `已选缓存文件：${data.filename || "-"}（热词 ${exportYearSummary.hotWords.length} 个）`;
    }

    _renderExportYearHotwords();
    _updateExportButtonState();
  } catch (e) {
    console.error("[Export] Failed to load cache:", e);
    showStatusMessage("error", "加载缓存失败");
    _renderExportYearHotwords();
    _updateExportButtonState();
  }
}

function initExportTabEnhancements() {
  _setExportYearSummaryVisible(true);

  document
    .getElementById("export-year-refresh")
    ?.addEventListener("click", async () => {
      await _loadGroupCacheList();
    });

  document
    .getElementById("export-group-cache")
    ?.addEventListener("change", async (e) => {
      await _loadGroupCacheDetail(e.target.value);
    });

  document
    .getElementById("export-year-auto-pick")
    ?.addEventListener("click", () => {
      exportYearSummary.selectedWords = new Set();
      (exportYearSummary.hotWords || []).slice(0, 8).forEach((it) => {
        const w = (it?.word ?? "").toString().trim();
        if (w) exportYearSummary.selectedWords.add(w);
      });
      _renderExportYearHotwords();
      _updateExportYearSelectedCount();
      _updateExportButtonState();
    });

  document
    .getElementById("export-year-clear")
    ?.addEventListener("click", () => {
      exportYearSummary.selectedWords = new Set();
      _renderExportYearHotwords();
      _updateExportYearSelectedCount();
      _updateExportButtonState();
    });

  document.getElementById("export-btn")?.addEventListener("click", async () => {
    await exportReport();
  });

  _loadGroupCacheList();
  _renderExportYearHotwords();
  _updateExportYearSelectedCount();
  _updateExportButtonState();
}

async function exportReport() {
  if (!exportYearSummary.selectedCache?.id) {
    showStatusMessage("error", "请先选择群体分析缓存");
    return;
  }
  if (exportYearSummary.selectedWords.size !== 8) {
    showStatusMessage("error", "请恰好选择 8 个热词");
    return;
  }

  try {
    _setExportBusy(true, "⏳ 正在导出年度总结（HTML），请稍候...");
    const response = await fetch(`${API_BASE}/export/html`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        template: _getExportTemplate(),
        cache_id: exportYearSummary.selectedCache.id,
        words: Array.from(exportYearSummary.selectedWords),
      }),
    });

    const contentType = (
      response.headers.get("content-type") || ""
    ).toLowerCase();
    if (contentType.includes("application/json")) {
      const data = await response.json();
      showStatusMessage("error", data.error || data.message || "导出失败");
      _setExportBusy(false, data.error || data.message || "导出失败");
      return;
    }

    if (!response.ok) {
      showStatusMessage("error", `导出失败（HTTP ${response.status}）`);
      _setExportBusy(false, `导出失败（HTTP ${response.status}）`);
      return;
    }

    const blob = await response.blob();
    const cd = response.headers.get("content-disposition") || "";
    let filename = "群聊年度总结.html";
    const m = cd.match(/filename\*=UTF-8''([^;]+)|filename="?([^";]+)"?/i);
    if (m) {
      filename = decodeURIComponent(m[1] || m[2] || filename);
    }

    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);

    showStatusMessage("success", "年度总结已导出（HTML）");
    _setExportBusy(
      false,
      "✅ 已导出（HTML），如未弹出下载请检查浏览器下载设置/拦截。",
    );
  } catch (error) {
    console.error("导出失败:", error);
    showStatusMessage("error", "导出失败");
    _setExportBusy(
      false,
      "❌ 导出失败：网络或服务异常（请重试，或查看控制台/Network 详情）",
    );
  } finally {
    _setExportBusy(
      false,
      document.getElementById("export-status")?.textContent || "",
    );
  }
}

document.addEventListener("DOMContentLoaded", () => {
  try {
    initExportTabEnhancements();
  } catch (e) {
    console.warn("[Export] init failed:", e);
  }
});
