/**
 * QQ聊天记录分析系统 - 预览模块
 * 负责预览筛选器、分页与记录渲染
 */

function markPreviewFiltersStale(_filename) {
  appState.previewFiltersLoadedForFile = null;
  appState.previewFiltersLoadingPromise = null;
}

async function ensurePreviewFiltersLoaded(filename) {
  const file = filename || appState.currentFile;
  if (!file) return;

  if (appState.previewFiltersLoadedForFile === file) return;
  if (appState.previewFiltersLoadingPromise)
    return appState.previewFiltersLoadingPromise;

  const dateSelect = document.getElementById("preview-date-filter");
  const qqSelect = document.getElementById("preview-qq-filter");
  if (dateSelect) {
    dateSelect.disabled = true;
    dateSelect.innerHTML = '<option value="">-- 加载中... --</option>';
  }
  if (qqSelect) {
    qqSelect.disabled = true;
    qqSelect.innerHTML = '<option value="">-- 加载中... --</option>';
  }

  const p = (async () => {
    try {
      await loadPreviewFilters(file);
    } finally {
      appState.previewFiltersLoadingPromise = null;
      if (appState.currentFile === file) {
        if (dateSelect) dateSelect.disabled = false;
        if (qqSelect) qqSelect.disabled = false;
      }
    }
  })();

  appState.previewFiltersLoadingPromise = p;
  return p;
}

async function loadPreviewFilters(filename) {
  const file = filename || appState.currentFile;
  if (!file) return;

  try {
    const response = await fetch(`${API_BASE}/preview/${file}/stats`);
    const data = await response.json();

    if (!data.success) {
      console.error("加载预览数据失败");
      return;
    }

    const dateSelect = document.getElementById("preview-date-filter");
    dateSelect.innerHTML = '<option value="">-- 所有日期 --</option>';
    data.dates.forEach((date) => {
      const option = document.createElement("option");
      option.value = date;
      option.textContent = date;
      dateSelect.appendChild(option);
    });

    const qqSelect = document.getElementById("preview-qq-filter");
    qqSelect.innerHTML = '<option value="">-- 所有成员 --</option>';
    data.qqs.forEach((item) => {
      const option = document.createElement("option");
      option.value = item.qq;
      const sender = (item.sender || "").toString().trim();
      option.textContent =
        sender && sender !== item.qq
          ? `${sender}(${item.qq})`
          : `QQ:${item.qq}`;
      qqSelect.appendChild(option);
    });

    if (appState.currentFile === file) {
      appState.previewFiltersLoadedForFile = file;
    }
  } catch (error) {
    console.error("加载预览数据失败:", error);
  }
}

async function loadChatRecords() {
  if (!appState.currentFile) {
    showStatusMessage("error", "请先加载文件");
    return;
  }

  if (typeof ensurePreviewFiltersLoaded === "function") {
    await ensurePreviewFiltersLoaded(appState.currentFile);
  }

  const dateFilter = document.getElementById("preview-date-filter");
  const qqFilter = document.getElementById("preview-qq-filter");
  const filterType = dateFilter.value ? "date" : qqFilter.value ? "qq" : "all";
  const filterValue = dateFilter.value || qqFilter.value || "";

  try {
    let url = `${API_BASE}/preview/${appState.currentFile}?page=${appState.previewData.currentPage}&page_size=${appState.previewData.pageSize}`;
    if (filterType !== "all") {
      url += `&filter_type=${filterType}&filter_value=${filterValue}`;
    }

    const response = await fetch(url);
    const data = await response.json();

    if (!data.success) {
      showStatusMessage("error", "加载失败");
      return;
    }

    appState.previewData.totalRecords = data.total;
    appState.previewData.totalPages = data.total_pages;

    displayChatRecords(data.records);
    updatePreviewPagination(data);
  } catch (error) {
    console.error("加载聊天记录失败:", error);
    showStatusMessage("error", "加载聊天记录失败");
  }
}

function displayChatRecords(records) {
  const tbody = document.getElementById("preview-records-body");
  tbody.innerHTML = "";

  if (records.length === 0) {
    document.getElementById("preview-records").style.display = "none";
    document.getElementById("preview-empty").style.display = "block";
    document.getElementById("preview-pagination").style.display = "none";
    document.getElementById("preview-stats").style.display = "none";
    return;
  }

  document.getElementById("preview-records").style.display = "block";
  document.getElementById("preview-empty").style.display = "none";
  document.getElementById("preview-pagination").style.display = "flex";
  document.getElementById("preview-stats").style.display = "block";

  records.forEach((record) => {
    const row = document.createElement("tr");
    row.innerHTML = `
            <td class="record-time">${record.timestamp}</td>
            <td>
                <div class="record-sender">${record.sender}</div>
                <div class="record-qq">${record.qq}</div>
            </td>
            <td class="record-content">${escapeHtml(record.content)}</td>
        `;
    tbody.appendChild(row);
  });
}

function updatePreviewPagination(data) {
  document.getElementById("preview-total").textContent = data.total;
  document.getElementById("preview-current-page").textContent = data.page;
  document.getElementById("preview-total-pages").textContent = data.total_pages;
  document.getElementById("preview-page-info").textContent =
    `第 ${data.page} / ${data.total_pages} 页`;

  document.getElementById("preview-prev-btn").disabled = data.page <= 1;
  document.getElementById("preview-next-btn").disabled =
    data.page >= data.total_pages;
}

function nextPreviewPage() {
  if (appState.previewData.currentPage < appState.previewData.totalPages) {
    appState.previewData.currentPage++;
    loadChatRecords();
  }
}

function prevPreviewPage() {
  if (appState.previewData.currentPage > 1) {
    appState.previewData.currentPage--;
    loadChatRecords();
  }
}
