<script setup>
import { reactive, ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from "vue";
import { FilterMatchMode } from "primevue/api";
import { useRouter } from "vue-router";
import { useToast } from "primevue/usetoast";
import { useAuth } from "@/service/AuthService";
import { useProject } from "@/service/ProjectService";
import { apiFetch } from "@/service/ApiLoader";
import ClearableMultiSelect from "@/components/ClearableMultiSelect.vue";
import AppLoader from "@/components/AppLoader.vue";

const router = useRouter();
const toast = useToast();
const { user, fullname, sessionExpired } = useAuth();
const { currentProject } = useProject();

// ---------- data ----------
const items = ref([]);
const loadingItems = ref(true);
const search = ref("");
const filterState = ref([]);
const filterIteration = ref([]);
const filterType = ref([]);
const filterParent = ref([]);
// filter PR: chỉ hiện item liên kết với pull request trong khoảng ngày chọn
// (Calendar range: mảng 1 hoặc 2 Date). Bỏ chọn = hết filter.
const prRange = ref(null);
const prIds = ref(new Set());
const prCount = ref(0);
// item theo PR: chọn 1/nhiều PR từ MultiSelect lazy-load, lọc item có link PR đó
const prFilter = ref([]);
const prIdsByPr = ref(new Set());
// danh sách PR cho MultiSelect: flat đã load, group theo ngày khi render
const prOptions = ref([]);
const PR_PAGE = 50;
const prListDone = ref(false);
const prListLoading = ref(false);
const prListBound = ref(false);
// spinner của table trong lúc fetch /api/pr-items
const prLoading = ref(false);
const prActive = computed(() => !!(prRange.value && prRange.value[0]));
const prNumberActive = computed(() => prFilter.value.length > 0);
// có filter nào đang bật (search / ngày PR / số PR / 4 MultiSelect) — đổi icon nút reset
const filterActive = computed(
  () =>
    !!search.value.trim() ||
    prActive.value ||
    prNumberActive.value ||
    filterState.value.length > 0 ||
    filterIteration.value.length > 0 ||
    filterType.value.length > 0 ||
    filterParent.value.length > 0,
);
const picked = reactive({ today: new Set(), next: new Set() });
// report thiếu display name thì dùng username thay thế? (Cài đặt)
const fullnameFallbackUser = ref(true);
const reportDate = ref(new Date());
const previewTab = ref(0);
const resultDialog = ref(false);
const resultTab = ref(0);
const taskBase = ref("");

// ---------- style giống dashboard ----------
const typeColors = {
  Epic: "#f97316",
  "User Story": "#3b82f6",
  Task: "#eab308",
  Bug: "#ef4444",
};
const stateStyles = ref({});
const textColorFor = (hex) => {
  const n = parseInt(hex.slice(1), 16);
  const [r, g, b] = [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  return 0.299 * r + 0.587 * g + 0.114 * b > 150 ? "#1f2937" : "#ffffff";
};
// % hoàn thành theo setting (percent_mode) — backend /api/items trả it.percent
const progressOf = (it) => it.percent ?? 0;

const stateOptions = computed(() =>
  [...new Set(items.value.map((i) => i.state))].sort(),
);
const typeOptions = computed(() =>
  [...new Set(items.value.map((i) => i.type))].sort(),
);
const parentOptions = computed(() =>
  [...new Set(items.value.map((i) => i.parent).filter(Boolean))]
    .sort((a, b) => a - b)
    .map((p) => {
      const it = items.value.find((i) => i.parent === p);
      return {
        label: it?.parentTitle ? `#${p} — ${it.parentTitle}` : `#${p}`,
        value: p,
      };
    }),
);
const iterationOptions = computed(() =>
  [...new Set(items.value.map((i) => i.iteration).filter(Boolean))]
    .sort()
    .reverse()
    .map((it) => ({ label: sprintLabel(it), value: it })),
);
// bỏ dấu tiếng Việt: nhập không dấu vẫn match tiêu đề có dấu (và ngược lại)
const noAccent = (s) =>
  String(s || "")
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/đ/g, "d")
    .replace(/Đ/g, "D")
    .toLowerCase();
const visibleItems = computed(() => {
  const q = noAccent(search.value).trim();
  const st = filterState.value;
  const fit = filterIteration.value;
  const ft = filterType.value;
  const fp = filterParent.value;
  return items.value.filter(
    (it) =>
      (!st.length || st.includes(it.state)) &&
      (!fit.length || fit.includes(it.iteration)) &&
      (!ft.length || ft.includes(it.type)) &&
      (!fp.length || fp.includes(it.parent)) &&
      (!prActive.value || prIds.value.has(it.id)) &&
      (!prNumberActive.value || prIdsByPr.value.has(it.id)) &&
      (!q ||
        String(it.id) === search.value.trim() ||
        noAccent(it.title).includes(q)),
  );
});
// sort theo iteration để item cùng sprint đứng cạnh nhau
const groupedItems = computed(() =>
  [...visibleItems.value]
    .sort((a, b) => (b.iteration || "").localeCompare(a.iteration || ""))
    // field lọc ghép "loại + tiêu đề" — filter cột Tiêu đề match cả 2
    .map((it) => ({ ...it, titleWithType: `${it.type} ${it.title}` })),
);
// filter theo cột trên header table (phễu) — kết hợp AND với filter ngoài bảng
const repFilters = ref({
  // format đầy đủ cho filterDisplay="menu" (constraints) — form đơn giản
  // {value, matchMode} crash khi đổi match mode (PrimeVue đọc .constraints[i])
  // key phải trùng filterField của cột Tiêu đề (lọc theo "loại + tiêu đề")
  titleWithType: {
    operator: "and",
    constraints: [{ value: null, matchMode: FilterMatchMode.CONTAINS }],
  },
  state: {
    operator: "and",
    constraints: [{ value: null, matchMode: FilterMatchMode.IN }],
  },
});
const sprintLabel = (it) =>
  (it || "").split("\\").pop() || "Không thuộc sprint";
// option filter có khi là string (state/type), có khi object {label, value}
const optionLabelOf = (o) => (typeof o === "string" ? o : o.label);

// ---------- load ----------
const loadItems = async () => {
  try {
    const r = await apiFetch("/api/items", { silent: true });
    if (r.status === 401) {
      sessionExpired(toast, router);
      return;
    }
    const j = await r.json();
    if (j.error) throw new Error(j.error);
    items.value = j.items;
    taskBase.value = j.taskBase || "";
    stateStyles.value = Object.fromEntries(
      Object.entries(j.stateColors || {}).map(([s, c]) => [
        s,
        { background: c, color: textColorFor(c) },
      ]),
    );
    if (j.fullname) {
      fullname.value = j.fullname;
    }
    fullnameFallbackUser.value = j.fullnameFallbackUser !== false;
  } catch (e) {
    toast.add({
      severity: "error",
      summary: "Lỗi tải work items",
      detail: e.message,
      life: 4000,
    });
  } finally {
    loadingItems.value = false;
  }
};

// Lưu Cài đặt (rules start/end, cách tính %, tên...) -> nạp lại items +
// ngày start/end để preview <pre> áp ngay config mới, không cần reload trang
const onSettingsUpdated = () => {
  loadItems();
  refreshStateDates();
};
onMounted(() => {
  reportDate.value = new Date();
  loadItems();
  window.addEventListener("settings-updated", onSettingsUpdated);
});
onBeforeUnmount(() => {
  window.removeEventListener("settings-updated", onSettingsUpdated);
});

// ---------- filter PR theo ngày ----------
const toISODate = (d) => {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
};
async function loadPrItems() {
  if (!prActive.value) {
    prIds.value = new Set();
    prCount.value = 0;
    return;
  }
  // range chưa đủ 2 ngày: coi ngày đầu là lọc 1 ngày
  const from = toISODate(prRange.value[0]);
  const to = prRange.value[1] ? toISODate(prRange.value[1]) : from;
  prLoading.value = true;
  try {
    const r = await apiFetch(`/api/pr-items?from=${from}&to=${to}`, {
      silent: true,
    });
    if (r.status === 401) {
      sessionExpired(toast, router);
      return;
    }
    const j = await r.json();
    if (j.error) throw new Error(j.error);
    prIds.value = new Set(j.ids || []);
    prCount.value = (j.prs || []).length;
  } catch (e) {
    toast.add({
      severity: "error",
      summary: "Lỗi tải pull requests",
      detail: e.message,
      life: 4000,
    });
    prRange.value = null;
  } finally {
    prLoading.value = false;
  }
}
watch(prRange, loadPrItems);

// đổi/bỏ khoảng ngày tạo PR -> danh sách option PR lọc theo ngày mới:
// reset list đã load, lazy load lại (panel đang mở thì nạp trang đầu ngay)
watch(prRange, () => {
  prOptions.value = [];
  prListDone.value = false;
  if (prPanelOpen.value) loadPrPage();
});

// ---------- item theo PR: MultiSelect lazy-load + group theo ngày ----------
// options giữ flat (append khi lazy load), group theo day khi render
const prGrouped = computed(() => {
  const out = [];
  let cur = null;
  for (const o of prOptions.value) {
    if (!cur || cur.label !== o.day) {
      cur = { label: o.day, items: [] };
      out.push(cur);
    }
    cur.items.push(o);
  }
  return out;
});

async function loadPrPage() {
  if (prListLoading.value || prListDone.value) return;
  prListLoading.value = true;
  try {
    const params = new URLSearchParams({
      skip: prOptions.value.length,
      top: PR_PAGE,
    });
    // đang chọn khoảng ngày tạo PR -> option PR cũng lọc theo khoảng đó
    if (prActive.value) {
      params.set("from", toISODate(prRange.value[0]));
      params.set(
        "to",
        prRange.value[1] ? toISODate(prRange.value[1]) : toISODate(prRange.value[0]),
      );
    }
    const r = await apiFetch(`/api/prs?${params}`, { silent: true });
    if (r.status === 401) {
      sessionExpired(toast, router);
      return;
    }
    const j = await r.json();
    if (j.error) throw new Error(j.error);
    prOptions.value.push(...(j.prs || []));
    if (!j.hasMore) prListDone.value = true;
  } catch (e) {
    toast.add({
      severity: "error",
      summary: "Lỗi tải danh sách PR",
      detail: e.message,
      life: 4000,
    });
    prListDone.value = true; // dừng lazy load, tránh loop lỗi
  } finally {
    prListLoading.value = false;
  }
}

// panel MultiSelect appendTo body: gắn scroll listener khi mở lần đầu,
// cuộn gần đáy thì load trang tiếp
const prPanelOpen = ref(false);
const onPrPanelScroll = (e) => {
  const el = e.target;
  if (el.scrollTop + el.clientHeight >= el.scrollHeight - 100) loadPrPage();
};
const onPrPanelShow = async () => {
  prPanelOpen.value = true;
  await loadPrPage(); // trang đầu
  if (prListBound.value) return;
  await nextTick();
  // scroll event không bubble: gắn đúng vào wrapper danh sách bên trong panel
  const scroller = document.querySelector(
    ".pr-select-panel .p-multiselect-items-wrapper",
  );
  if (!scroller) return;
  scroller.addEventListener("scroll", onPrPanelScroll, { passive: true });
  prListBound.value = true;
};

// chọn PR -> load item của các PR đó
async function loadPrItemsByPrs() {
  if (!prNumberActive.value) {
    prIdsByPr.value = new Set();
    return;
  }
  prLoading.value = true;
  try {
    const r = await apiFetch(`/api/pr-items?prs=${prFilter.value.join(",")}`, {
      silent: true,
    });
    if (r.status === 401) {
      sessionExpired(toast, router);
      return;
    }
    const j = await r.json();
    if (j.error) throw new Error(j.error);
    prIdsByPr.value = new Set(j.ids || []);
    // item được add vào PR nhưng không gán cho user (US người khác...) —
    // thêm vào table để hiện được khi filter PR đang chọn
    const known = new Set(items.value.map((i) => i.id));
    const extra = (j.items || []).filter((i) => !known.has(i.id));
    if (extra.length) items.value.push(...extra);
  } catch (e) {
    toast.add({
      severity: "error",
      summary: "Lỗi tải pull requests",
      detail: e.message,
      life: 4000,
    });
    prFilter.value = [];
  } finally {
    prLoading.value = false;
  }
}
watch(prFilter, loadPrItemsByPrs);

// ---------- pick ----------
const rows = ref(10);
const onPage = (e) => (rows.value = e.rows);
function toggle(id, group) {
  picked[group].has(id) ? picked[group].delete(id) : picked[group].add(id);
}
// checkbox header: tất cả item đang lọc đã được chọn ở nhóm đó chưa
const allPicked = (group) =>
  visibleItems.value.length > 0 &&
  visibleItems.value.every((i) => picked[group].has(i.id));
function toggleAll(group) {
  const vis = visibleItems.value.map((i) => i.id);
  const allOn = allPicked(group);
  vis.forEach((id) =>
    allOn ? picked[group].delete(id) : picked[group].add(id),
  );
}
function clearPick() {
  picked.today.clear();
  picked.next.clear();
  // clear toàn bộ filter: date PR, số PR, search, các MultiSelect
  prRange.value = null; // watch sẽ reset prIds/prCount
  prFilter.value = []; // watch sẽ reset prIdsByPr
  search.value = "";
  filterState.value = [];
  filterIteration.value = [];
  filterType.value = [];
  filterParent.value = [];
}
function rowClass(data) {
  return {
    "bg-primary-reverse": picked.today.has(data.id) || picked.next.has(data.id),
  };
}

// ---------- render markdown ----------
const escapeMd = (s) =>
  String(s || "")
    .replace(/\|/g, "\\|")
    .replace(/\n/g, " ")
    .trim();
const ddMMyyyy = (d) => {
  const p = (n) => String(n).padStart(2, "0");
  return `${p(d.getDate())}/${p(d.getMonth() + 1)}/${d.getFullYear()}`;
};

const todayItems = computed(() =>
  items.value.filter((it) => picked.today.has(it.id)),
);
const nextItems = computed(() =>
  items.value.filter((it) => picked.next.has(it.id)),
);

const chatMd = computed(() => {
  const dateStr = ddMMyyyy(reportDate.value);
  const who =
    fullname.value ||
    (fullnameFallbackUser.value ? user.value : "") ||
    "...";
  const lines = [
    `*Báo cáo nhân sự* ${dateStr}`,
    `*Nhân sự:* ${who}`,
    "*Công việc:*",
  ];
  for (const it of todayItems.value)
    lines.push(`- ${escapeMd(it.type)} ${it.id}: ${escapeMd(it.title)} (${it.percent ?? 100}%)`);
  if (!todayItems.value.length) lines.push("- ...");
  lines.push("*Công việc ngày tiếp theo:*");
  for (const it of nextItems.value)
    lines.push(`- ${escapeMd(it.type)} ${it.id}: ${escapeMd(it.title)} (${it.percent ?? 100}%)`);
  if (!nextItems.value.length) lines.push("- ...");
  lines.push("*Vấn đề:*", "- None");
  return lines.join("\n");
});

const larkMd = computed(() => {
  // Start/End date Lark theo format yyyy-mm-dd
  const dateStr = toISODate(reportDate.value);
  const merged = [];
  const seen = new Set();
  for (const it of [...todayItems.value, ...nextItems.value]) {
    if (!seen.has(it.id)) {
      seen.add(it.id);
      merged.push(it);
    }
  }
  const lines = [
    "| Status | Start date | End date | OT | Note | Type | Task ID | Task Name | Task Link |",
    "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
  ];
  for (const it of merged) {
    const link = taskBase.value ? `${taskBase.value}${it.id}` : `${it.id}`;
    // có ngày vào trạng thái (rules cấu hình) thì dùng, không thì fallback
    // (stateDates/endDates đã là yyyy-mm-dd nên giữ nguyên)
    const start = stateDates.value[it.id] || dateStr;
    const end = endDates.value[it.id] || "";
    lines.push(
      `| ${escapeMd(it.state)} | ${start} | ${end} |  |  | ${escapeMd(it.type)} | ${
        it.id
      } | ${escapeMd(it.title)} | ${link} |`,
    );
  }
  return lines.join("\n");
});

// ---------- start/end date Lark theo trạng thái ----------
// Cấu hình "Trạng thái bắt đầu/kết thúc (Lark)" trong Cài đặt: khi có,
// Start/End date bảng Lark = ngày item chuyển sang trạng thái đó (server
// đọc revisions TFS). Lấy async theo item đang chọn (debounce, chỉ item
// được chọn nên ít call); chưa có ngày thì fallback như cũ (start = ngày
// báo cáo, end = trống).
const stateDates = ref({});
const endDates = ref({});
let stateDatesTimer = null;
const refreshStateDates = () => {
  const ids = [...picked.today, ...picked.next];
  clearTimeout(stateDatesTimer);
  if (!ids.length) {
    stateDates.value = {};
    endDates.value = {};
    return;
  }
  stateDatesTimer = setTimeout(async () => {
    try {
      const r = await apiFetch(`/api/state-dates?ids=${ids.join(",")}`, {
        silent: true,
      });
      if (!r.ok) return;
      const j = await r.json();
      stateDates.value = j.startDates || {};
      endDates.value = j.endDates || {};
    } catch {
      // lỗi mạng — giữ fallback
    }
  }, 400);
};
watch(() => [...picked.today, ...picked.next], refreshStateDates);

const previewMd = computed(() => {
  if (previewTab.value === 0) return chatMd.value;
  if (previewTab.value === 1) return larkMd.value;
  return chatMd.value + "\n\n" + larkMd.value;
});

// preview cho phép sửa tay: mỗi tab giữ bản edit riêng, dirty = người dùng đã sửa
const baseOf = (t) =>
  t === 0
    ? chatMd.value
    : t === 1
    ? larkMd.value
    : chatMd.value + "\n\n" + larkMd.value;
const edited = reactive({ 0: "", 1: "", 2: "" });
const dirty = reactive({ 0: false, 1: false, 2: false });
const tabText = computed({
  get: () =>
    dirty[previewTab.value]
      ? edited[previewTab.value]
      : baseOf(previewTab.value),
  set: (v) => {
    edited[previewTab.value] = v;
    dirty[previewTab.value] = true;
  },
});
// chọn item / đổi ngày / đổi tên thì sinh lại, bỏ edit cũ
watch([todayItems, nextItems, reportDate, fullname], () =>
  [0, 1, 2].forEach((t) => (dirty[t] = false)),
);
// reset tab hiện tại về nội dung sinh tự động
const resetTab = () => (dirty[previewTab.value] = false);
// reset cả 3 tab + clear chọn item bên table
const resetAll = () => {
  [0, 1, 2].forEach((t) => (dirty[t] = false));
  clearPick();
};

// ---------- report ----------
// nội dung report theo tab, giữ edit tay của người dùng nếu có
const reportOf = (t) => (dirty[t] ? edited[t] : baseOf(t));

function makeReport() {
  if (!picked.today.size && !picked.next.size) {
    toast.add({
      severity: "warn",
      summary: "Rỗng",
      detail: "Chưa chọn item",
      life: 4000,
    });
    return;
  }
  resultTab.value = 0;
  resultDialog.value = true;
}

// ink-bar của TabView đo offset qua getBoundingClientRect lúc mount,
// đang giữa lúc dialog animate (scale 150ms) nên đo lệch. Dialog emit
// 'show' ở onEnter (đầu animation) — phải đợi animation xong mới đo lại.
const resultTabView = ref(null);
const reflowInkBar = () =>
  setTimeout(() => resultTabView.value?.updateInkBar?.(), 200);

// dialog cho sửa tay: dùng chung edited/dirty với preview ngoài —
// sửa ở đâu thì copy/tải file ở cả hai chỗ đều thấy.
// Tab dialog xếp Full, Chat, Lark — map về index nội dung 0=chat,1=lark,2=full
const dialogTabIndexMap = [2, 0, 1];
const resultText = computed({
  get: () => reportOf(dialogTabIndexMap[resultTab.value]),
  set: (v) => {
    const t = dialogTabIndexMap[resultTab.value];
    edited[t] = v;
    dirty[t] = true;
  },
});

// dialog đổi tab thì preview ngoài nhảy về tab nội dung tương ứng —
// sửa trong dialog xong đóng lại, card ngoài đang đúng tab, thấy ngay thay đổi
watch(resultTab, (i) => (previewTab.value = dialogTabIndexMap[i]));

const reportFileName = () =>
  `bao-cao-${ddMMyyyy(reportDate.value).replaceAll("/", "-")}.md`;

function downloadReport() {
  const blob = new Blob([resultText.value], {
    type: "text/markdown;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = reportFileName();
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  toast.add({ severity: "success", summary: "Đã tải file", life: 1500 });
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    toast.add({ severity: "success", summary: "Đã copy", life: 1500 });
  } catch (e) {
    try {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
      toast.add({ severity: "success", summary: "Đã copy", life: 1500 });
    } catch (e2) {
      toast.add({ severity: "error", summary: "Không copy được", life: 2000 });
    }
  }
}
</script>

<template>
  <div class="grid">
    <!-- item picker -->
    <div class="col-12 xl:col-7">
      <div class="card">
        <div class="flex align-items-center mb-3">
          <h5 class="m-0 flex align-items-center">
            Chọn công việc
            <Tag v-if="currentProject" :value="currentProject" class="ml-2" />
          </h5>
        </div>
        <div class="flex gap-2 mb-3">
          <ClearableMultiSelect
            v-model="filterState"
            :options="stateOptions"
            placeholder="State"
            :filter="true"
            class="flex-1 min-w-0"
            panelClass="report-filter-panel">
            <template #option="s">
              <span
                class="filter-option"
                v-tooltip.bottom="optionLabelOf(s.option)"
                >{{ optionLabelOf(s.option) }}</span
              >
            </template>
          </ClearableMultiSelect>
          <ClearableMultiSelect
            v-model="filterIteration"
            :options="iterationOptions"
            optionLabel="label"
            optionValue="value"
            placeholder="Sprint"
            :filter="true"
            class="flex-1 min-w-0"
            panelClass="report-filter-panel">
            <template #option="s">
              <span
                class="filter-option"
                v-tooltip.bottom="optionLabelOf(s.option)"
                >{{ optionLabelOf(s.option) }}</span
              >
            </template>
          </ClearableMultiSelect>
          <ClearableMultiSelect
            v-model="filterType"
            :options="typeOptions"
            placeholder="Type"
            :filter="true"
            class="flex-1 min-w-0"
            panelClass="report-filter-panel">
            <template #option="s">
              <span
                class="filter-option"
                v-tooltip.bottom="optionLabelOf(s.option)"
                >{{ optionLabelOf(s.option) }}</span
              >
            </template>
          </ClearableMultiSelect>
          <ClearableMultiSelect
            v-model="filterParent"
            :options="parentOptions"
            optionLabel="label"
            optionValue="value"
            placeholder="Parent"
            :filter="true"
            class="flex-1 min-w-0"
            panelClass="report-filter-panel">
            <template #option="s">
              <span
                class="filter-option"
                v-tooltip.bottom="optionLabelOf(s.option)"
                >{{ optionLabelOf(s.option) }}</span
              >
            </template>
          </ClearableMultiSelect>
        </div>
        <!-- Ngày tạo PR + Item theo PR luôn cùng 1 dòng -->
        <div class="flex gap-2 mb-2 flex-nowrap">
          <Calendar
            v-model="prRange"
            selectionMode="range"
            showButtonBar
            showIcon
            iconDisplay="input"
            :manualInput="false"
            placeholder="Ngày tạo PR"
            dateFormat="dd/mm/yy"
            class="pr-range-cal flex-1">
            <!-- cụm icon bên phải field: ✕ xóa range + chip số PR + branch/spinner.
                 Đặt chung 1 flex để tự xếp cạnh nhau, không overlap khi chip rộng -->
            <template #inputicon="slotProps">
              <span class="pr-field-icons">
                <i
                  v-if="prActive && !prLoading"
                  class="pi pi-times pr-clear-date-icon"
                  @click.stop="prRange = null"></i>
                <span
                  v-if="prActive && !prLoading"
                  class="pr-count-icon"
                  @click="slotProps.clickCallback"
                  >{{ prCount }} PR</span
                >
                <i
                  v-if="prLoading"
                  class="pi pi-spin pi-spinner pr-spinner-icon"
                  @click="slotProps.clickCallback"></i>
                <img
                  v-else
                  src="/icons/code-branch-icon.svg"
                  alt=""
                  class="pr-branch-icon"
                  @click="slotProps.clickCallback" />
              </span>
            </template>
          </Calendar>
          <ClearableMultiSelect
            v-model="prFilter"
            :options="prGrouped"
            optionGroupLabel="label"
            optionGroupChildren="items"
            optionLabel="label"
            optionValue="value"
            placeholder="Pull Request"
            :filter="true"
            filterPlaceholder="Tìm PR..."
            scrollHeight="12rem"
            appendTo="self"
            class="flex-1 min-w-0"
            panelClass="pr-select-panel"
            @show="onPrPanelShow"
            @hide="prPanelOpen = false">
            <template #option="s">
              <span
                class="filter-option"
                v-tooltip.bottom="optionLabelOf(s.option)"
                >{{ optionLabelOf(s.option) }}</span
              >
            </template>
          </ClearableMultiSelect>
        </div>
        <!-- search + reset filter cùng hàng: search fill chỗ còn lại -->
        <div class="flex gap-2 mb-4 flex-nowrap align-items-center">
          <IconField iconPosition="left" class="flex-1 min-w-0">
            <InputIcon class="pi pi-search" />
            <InputText
              v-model="search"
              placeholder="Tìm theo ID hoặc tiêu đề..."
              class="w-full" />
          </IconField>
          <Button
            label="Reset filter"
            :icon="filterActive ? 'pi pi-filter' : 'pi pi-filter-slash'"
            class="p-button-outlined p-button-danger p-button-sm flex-shrink-0"
            @click="clearPick" />
        </div>
        <DataTable
          :value="groupedItems"
          :loading="loadingItems || prLoading"
          :rows="rows"
          scrollable
          scrollHeight="47vh"
          :rowsPerPageOptions="[5, 10, 20, 50, 100]"
          v-model:filters="repFilters"
          filterDisplay="menu"
          @page="onPage"
          :paginator="true"
          dataKey="id"
          responsiveLayout="scroll"
          :rowClass="rowClass"
          currentPageReportTemplate="Hiện {first}-{last} / {totalRecords}"
          paginatorTemplate="FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink RowsPerPageDropdown CurrentPageReport">
          <template #empty>
            <div
              class="flex min-h-52 flex-column align-items-center justify-content-center py-5 text-500">
              <i
                v-if="!loadingItems && !prLoading"
                class="pi pi-inbox text-4xl mb-2"></i>
              <span v-if="!loadingItems && !prLoading">Không có dữ liệu</span>
            </div>
          </template>
          <template #loading>
            <div class="flex flex-col items-center gap-2">
              <AppLoader />
            </div>
          </template>
          <Column
            field="id"
            header="ID"
            :sortable="true"
            style="width: 5rem"
            frozen>
            <template #body="slotProps">
              <a
                :href="taskBase + slotProps.data.id"
                target="_blank"
                rel="noopener"
                class="font-medium text-primary"
                v-tooltip.bottom="'Xem work item'"
                >#{{ slotProps.data.id }}</a
              >
            </template>
          </Column>
          <Column
            field="title"
            header="Tiêu đề"
            :sortable="true"
            :filter="true"
            filterField="titleWithType"
            style="width: 40%">
            <template #body="slotProps">
              <div class="flex align-items-center" style="column-gap: 0.5rem">
                <span
                  class="text-sm font-medium flex-shrink-0"
                  :style="{
                    color: typeColors[slotProps.data.type] || '#6b7280',
                  }"
                  >{{ slotProps.data.type }}</span
                >
                <span
                  class="one-line flex-1 min-w-0"
                  v-tooltip.bottom="slotProps.data.title"
                  >{{ slotProps.data.title }}</span
                >
              </div>
              <div
                class="flex align-items-center flex-wrap mt-1"
                style="column-gap: 0.5rem">
                <ProgressBar
                  :value="progressOf(slotProps.data)"
                  :showValue="false"
                  style="height: 4px; width: 8rem" />
                <span class="italic text-500 text-sm w-2rem"
                  >{{ progressOf(slotProps.data) }}%</span
                >
              </div>
            </template>
            <template #filter="{ filterModel, filterCallback }">
              <InputText
                v-model="filterModel.value"
                @keydown.enter="filterCallback()"
                class="p-column-filter"
                placeholder="Loại hoặc tiêu đề" />
            </template>
          </Column>
          <Column
            field="state"
            header="Trạng thái"
            :sortable="true"
            :filter="true"
            :showFilterMatchModes="false"
            :filterMenuStyle="{ width: '14rem' }"
            style="min-width: 15rem">
            <template #body="slotProps">
              <Tag
                :value="slotProps.data.state"
                class="white-space-nowrap"
                :style="
                  stateStyles[slotProps.data.state] || {
                    background: '#b2b2b2',
                    color: '#1f2937',
                  }
                " />
            </template>
            <template #filter="{ filterModel }">
              <MultiSelect
                v-model="filterModel.value"
                :options="stateOptions"
                placeholder="Chọn trạng thái"
                class="p-column-filter"
                :showClear="true"
                :maxSelectedLabels="4" />
            </template>
          </Column>
          <Column style="min-width: 5rem" frozen alignFrozen="right">
            <template #header>
              <Checkbox
                :modelValue="allPicked('next')"
                binary
                @update:modelValue="toggleAll('next')" />
              <span class="ml-2">Mới</span>
            </template>
            <template #body="slotProps">
              <div class="flex align-items-center items-center justify-center">
                <Checkbox
                  :modelValue="picked.next.has(slotProps.data.id)"
                  binary
                  @update:modelValue="toggle(slotProps.data.id, 'next')" />
              </div>
            </template>
          </Column>
          <Column style="min-width: 5rem" frozen alignFrozen="right">
            <template #header>
              <Checkbox
                :modelValue="allPicked('today')"
                binary
                @update:modelValue="toggleAll('today')" />
              <span class="ml-2">Cũ</span>
            </template>
            <template #body="slotProps">
              <div class="flex align-items-center items-center justify-center">
                <Checkbox
                  :modelValue="picked.today.has(slotProps.data.id)"
                  binary
                  @update:modelValue="toggle(slotProps.data.id, 'today')" />
              </div>
            </template>
          </Column>
        </DataTable>
      </div>
    </div>

    <!-- right: preview + report -->
    <div class="col-12 xl:col-5">
      <div class="card">
        <h5 class="m-0 mb-4">Xem trước report</h5>
        <div class="flex flex-wrap gap-3 align-items-center mb-4">
          <Calendar
            v-model="reportDate"
            dateFormat="dd/mm/yy"
            :showIcon="true"
            class="flex-1" />
          <Button
            label="Tạo report"
            icon="pi pi-file"
            @click="makeReport"
            class="make-report-btn flex-none" />
        </div>

        <div class="relative">
          <TabView v-model:activeIndex="previewTab">
            <TabPanel header="Chat">
              <div class="pre-wrap">
                <div class="pre-actions">
                  <Button
                    icon="pi pi-refresh"
                    class="p-button-text p-button-sm"
                    aria-label="Reset về nội dung tự động"
                    :disabled="!dirty[previewTab]"
                    @click="resetTab" />
                  <Button
                    icon="pi pi-copy"
                    class="p-button-text p-button-sm"
                    aria-label="Copy"
                    @click="copyText(tabText)" />
                </div>
                <textarea
                  v-model="tabText"
                  class="preview-input"
                  wrap="off"
                  spellcheck="false"></textarea>
              </div>
            </TabPanel>
            <TabPanel header="Lark">
              <div class="pre-wrap">
                <div class="pre-actions">
                  <Button
                    icon="pi pi-refresh"
                    class="p-button-text p-button-sm"
                    aria-label="Reset về nội dung tự động"
                    :disabled="!dirty[previewTab]"
                    @click="resetTab" />
                  <Button
                    icon="pi pi-copy"
                    class="p-button-text p-button-sm"
                    aria-label="Copy"
                    @click="copyText(tabText)" />
                </div>
                <textarea
                  v-model="tabText"
                  class="preview-input"
                  wrap="off"
                  spellcheck="false"></textarea>
              </div>
            </TabPanel>
            <TabPanel header="Full">
              <div class="pre-wrap">
                <div class="pre-actions">
                  <Button
                    icon="pi pi-refresh"
                    class="p-button-text p-button-sm"
                    aria-label="Reset về nội dung tự động"
                    :disabled="!dirty[previewTab]"
                    @click="resetTab" />
                  <Button
                    icon="pi pi-copy"
                    class="p-button-text p-button-sm"
                    aria-label="Copy"
                    @click="copyText(tabText)" />
                </div>
                <textarea
                  v-model="tabText"
                  class="preview-input"
                  wrap="off"
                  spellcheck="false"></textarea>
              </div>
            </TabPanel>
          </TabView>
          <Button
            icon="pi pi-refresh"
            class="p-button-outlined p-button-sm reset-all-btn"
            v-tooltip.bottom="'Reset preview cả 3 tab'"
            @click="resetAll" />
        </div>
      </div>
    </div>

    <!-- result dialog: xem trước + tải file -->
    <Dialog
      v-model:visible="resultDialog"
      modal
      header="Xem trước report"
      class="report-dialog"
      :style="{ width: '70vw', height: '85vh' }"
      :contentStyle="{
        flex: '1',
        minHeight: '0',
        display: 'flex',
        overflow: 'hidden',
      }"
      @show="reflowInkBar">
      <div class="relative">
        <TabView ref="resultTabView" v-model:activeIndex="resultTab">
          <TabPanel header="Full">
            <div class="report-pre-wrap">
              <textarea
                v-model="resultText"
                class="report-pre"
                spellcheck="false"></textarea>
            </div>
          </TabPanel>
          <TabPanel header="Chat">
            <div class="report-pre-wrap">
              <textarea
                v-model="resultText"
                class="report-pre"
                spellcheck="false"></textarea>
            </div>
          </TabPanel>
          <TabPanel header="Lark">
            <div class="report-pre-wrap">
              <textarea
                v-model="resultText"
                class="report-pre"
                spellcheck="false"></textarea>
            </div>
          </TabPanel>
        </TabView>
        <!-- nút nằm cùng hàng tab, dạt phải — giống reset-all ở preview ngoài -->
        <div class="dialog-tab-actions">
          <Button
            label="Copy"
            icon="pi pi-copy"
            class="p-button-outlined p-button-sm"
            @click="copyText(resultText)" />
          <Button
            :label="`Tải file (${reportFileName()})`"
            icon="pi pi-download"
            class="p-button-sm"
            @click="downloadReport" />
        </div>
      </div>
    </Dialog>
  </div>
</template>

<style scoped>
/* tiêu đề table: 1 dòng, dài quá thì ... */
.one-line {
  display: block;
  max-width: 100%;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

/* Calendar range filter PR: chia đều hàng với MultiSelect PR (flex-1 mỗi bên) */
.pr-range-cal {
  position: relative;
  flex: 1 1 0;
  min-width: 0;
}

/* cụm icon phải của ô date PR: absolute 1 chỗ, các icon bên trong xếp flex
   cạnh nhau theo gap — chip "12 PR" rộng bao nhiêu ✕ cũng không đè */
.pr-field-icons {
  position: absolute;
  top: 50%;
  right: 0.75rem;
  transform: translateY(-50%);
  display: flex;
  align-items: center;
  gap: 0.5rem;
  z-index: 1;
}

/* chip số PR thay icon calendar khi filter active */
.pr-count-icon {
  font-size: 0.75rem;
  font-weight: 600;
  line-height: 1.5;
  padding: 0 0.4rem;
  border-radius: var(--content-border-radius, 6px);
  background: var(--primary-color);
  color: var(--primary-color-text);
  cursor: pointer;
  white-space: nowrap;
}

/* nút "Tạo report": theme cho .p-button-label flex 1 1 auto — nút flex-1 rộng
   làm icon dạt trái, label giãn giữa, tách rời nhau. Giữ label auto + cụm
   icon-label sát nhau nằm giữa nút. */
.make-report-btn {
  justify-content: center;
}

.make-report-btn :deep(.p-button-label) {
  flex: 0 1 auto;
}

.make-report-btn :deep(.p-button-icon) {
  margin-right: 0.5rem;
}

/* nút ✕ xóa khoảng ngày tạo PR */
.pr-clear-date-icon {
  cursor: pointer;
  font-size: 0.875rem;
  color: var(--text-color-secondary);
}

.pr-clear-date-icon:hover {
  color: var(--text-color);
}

.pr-spinner-icon {
  cursor: pointer;
}

/* icon branch size chuẩn icon PrimeVue */
.pr-branch-icon {
  width: 1.5rem;
  height: 1.5rem;
  opacity: 0.4;
  cursor: pointer;
}

.pr-range-cal :deep(.p-inputtext) {
  width: 100%;
  font-size: 0.875rem;
}

/* table-layout fixed: giữ width cột, td không giãn theo nội dung —
   ellipsis của .one-line mới hoạt động */
:deep(.p-datatable-table) {
  table-layout: fixed;
}

/* thead sticky: PrimeVue v3 không sticky sẵn thead cho table scrollable.
   ProgressBar trong cell là position:relative (theme) nên vẽ đè lên thead
   thường khi cuộn — ghim thead, z-index cao hơn cả Progressbar lẫn
   cột frozen (z-index 1 của theme). */
:deep(
    .p-datatable-scrollable
      > .p-datatable-wrapper
      > .p-datatable-table
      > .p-datatable-thead
  ) {
  position: sticky;
  top: 0;
  z-index: 2;
}

/* td cột frozen: theme chỉ sticky chứ không set z-index (th mới có z-1),
   cùng z-auto với ProgressBar nhưng đứng trước trong DOM nên bị đè khi
   cuộn ngang. Nâng lên 1 để nằm trên mọi content z-auto trong tbody. */
:deep(.p-datatable .p-datatable-tbody > tr > td.p-frozen-column) {
  z-index: 1;
}

/* vùng sửa preview: nền tối chung cho strip nút + textarea, cao theo viewport */
.pre-wrap {
  position: relative;
  height: calc(100vh - 28rem);
  margin-top: 0.75rem; /* thay padding panels đã bỏ */
  display: flex;
  flex-direction: column;
  background: #111827;
  border-radius: 6px;
  overflow: hidden;
}

/* bỏ padding mặc định của panels (tạo khoảng trắng thừa dưới pre) */
:deep(.p-tabview-panels) {
  padding: 0;
}

.preview-input {
  display: block;
  flex: 1;
  min-height: 0; /* cho phép co lại, scroll nằm trong textarea */
  width: 100%;
  margin: 0;
  padding: 0.75rem;
  border: none;
  outline: none;
  resize: none;
  overflow-y: auto;
  overflow-x: hidden;
  white-space: pre-wrap; /* rớt dòng, không cuộn ngang */
  overflow-wrap: anywhere;
  background: transparent;
  color: #f3f4f6;
  font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas,
    monospace;
  font-size: 0.875rem;
  line-height: 1.5;
  /* scrollbar đồng nhất với nền tối */
  scrollbar-width: thin;
  scrollbar-color: #374151 #111827;
}

.preview-input::-webkit-scrollbar {
  width: 8px;
  background: #111827;
}

.preview-input::-webkit-scrollbar-thumb {
  background: #374151;
  border-radius: 4px;
}

.preview-input::-webkit-scrollbar-thumb:hover {
  background: #4b5563;
}

/* strip nút reset + copy riêng trên cùng, không nằm trong vùng scroll */
.pre-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.25rem;
  padding: 0.25rem 0.25rem 0;
}

.pre-actions :deep(.p-button) {
  color: #9ca3af;
}

.pre-actions :deep(.p-button:hover) {
  background: rgba(255, 255, 255, 0.1);
  color: #f9fafb;
}

/* tab dùng layout mặc định PrimeVue: label căn giữa nav,
   active indicator (box-shadow inset đáy link) nằm trên border nav.
   Không tự thêm padding-bottom cho li/a — đẩy indicator ra khỏi
   đường kẻ thành cục đen lệch dưới. */

/* nút reset-all nằm trong hàng tab, dạt phải */
.reset-all-btn {
  position: absolute;
  top: 0.3rem;
  right: 0;
}

/* chừa chỗ bên phải nav để nút reset-all không đè lên tab cuối;
   border-bottom khai báo lại tường minh — nav thành scroll container
   (mobile) làm border của theme không vẽ hết chiều rộng */
:deep(.p-tabview-nav) {
  padding-right: 3rem;
  border-bottom: 1px solid var(--surface-border);
}

/* mobile: tab không xuống dòng (wrap làm đứt border-bottom nav),
   nav cuộn ngang thay vì rớt hàng */
@media (max-width: 767px) {
  :deep(.p-tabview-nav) {
    flex-wrap: nowrap;
    overflow-x: auto;
    scrollbar-width: none; /* Firefox: ẩn scrollbar */
  }

  :deep(.p-tabview-nav::-webkit-scrollbar) {
    display: none; /* Chrome: ẩn scrollbar */
  }
}

/* header không rớt dòng */
:deep(.p-datatable-thead > tr > th) {
  white-space: nowrap;
}

/* Tag Trạng thái: 1 dòng */
:deep(.p-tag) {
  white-space: nowrap;
}
</style>

<style>
/*
 * CSS dialog report — KHÔNG scoped: PrimeVue Dialog mặc định appendTo="body",
 * teleport ra ngoài #app, selector :deep() scoped không có ancestor data-v
 * nên không match. Tiền tố .report-dialog để không leak ra ngoài dialog này.
 */
.report-dialog.p-dialog {
  width: 70vw;
  height: 85vh;
  display: flex;
  flex-direction: column; /* content flex:1 fill hết chỗ còn lại sau header */
}

/* content không cuộn: chuỗi flex min-height 0 đẩy scroll xuống pre.
   Bắt đầu từ wrapper .relative bọc TabView + nút (content display flex) */
.report-dialog .p-dialog-content > .relative {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}
.report-dialog .p-tabview {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}
/* nút hành động nằm trong hàng tab, dạt phải — phủ đúng chiều cao
   nav tab để cụm nút căn giữa theo hàng tab, không bị đẩy lên trên */
.report-dialog .dialog-tab-actions {
  position: absolute;
  top: 0;
  right: 0;
  height: 3rem; /* chiều cao .p-tabview-nav (padding .75rem 1rem + text) */
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

/* icon/label căn giữa theo cả 2 chiều trong nút */
.report-dialog .dialog-tab-actions .p-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
/* chừa chỗ bên phải nav để nút không đè lên tab cuối */
.report-dialog .p-tabview-nav {
  padding-right: 1rem;
}

/* nút chỉ hiện icon khi dialog hẹp — áp cả 2: viewport < md,
   hoặc dialog (70vw) hẹp hơn 36rem trên màn mid-size */
.report-dialog.p-dialog {
  container-type: inline-size;
}

@media (max-width: 767px) {
  .report-dialog .dialog-tab-actions .p-button .p-button-label {
    display: none;
  }

  .report-dialog .dialog-tab-actions .p-button .p-button-icon {
    margin-right: 0;
  }

  .report-dialog .dialog-tab-actions .p-button {
    padding: 0.4375rem 0.7rem;
  }
}

@container (max-width: 36rem) {
  .report-dialog .dialog-tab-actions .p-button .p-button-label {
    display: none;
  }

  .report-dialog .dialog-tab-actions .p-button .p-button-icon {
    margin-right: 0;
  }

  .report-dialog .dialog-tab-actions .p-button {
    padding: 0.4375rem 0.7rem;
  }
}

.report-dialog .p-tabview-panels {
  display: flex;
  flex: 1;
  min-height: 0;
  padding: 0; /* bỏ padding ngoài của panels, pre tự có padding riêng */
}
.report-dialog .p-tabview-panel {
  display: flex;
  flex: 1;
  min-height: 0;
  padding-top: 1rem;
}

/* nội dung report trong dialog: wrapper giữ radius + overflow hidden
   để clip scrollbar góc vuông; pre trong suốt cuộn bên trong */
.report-dialog .report-pre-wrap {
  flex: 1;
  min-height: 0;
  border-radius: 6px;
  background: #111827;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* textarea sửa được trong dialog — style giống pre cũ */
.report-dialog .report-pre {
  display: block;
  flex: 1;
  min-height: 0;
  width: 100%;
  margin: 0;
  padding: 1.25rem;
  border: none;
  outline: none;
  resize: none;
  background: transparent;
  color: #f3f4f6;
  font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas,
    monospace;
  font-size: 0.875rem;
  line-height: 1.5;
  white-space: pre-wrap; /* rớt dòng, không cuộn ngang */
  overflow-wrap: anywhere;
  overflow: auto;
  /* scrollbar đồng nhất với nền tối */
  scrollbar-width: thin;
  scrollbar-color: #374151 #111827;
}

/* giống scrollbar .preview-input ngoài dialog */
.report-dialog .report-pre::-webkit-scrollbar {
  width: 8px;
  background: transparent;
}

.report-dialog .report-pre::-webkit-scrollbar-thumb {
  background: #374151;
  border-radius: 4px;
}

.report-dialog .report-pre::-webkit-scrollbar-thumb:hover {
  background: #4b5563;
}

/*
 * Panel dropdown của 4 MultiSelect filter — panel mặc định appendTo="body"
 * nên viết KHÔNG scoped, chọn theo class panelClass gắn ở template.
 * Panel giãn theo option dài nhất nhưng capped — option vượt cap thì
 * "..." (ellipsis), hover vào hiện tooltip full text (v-tooltip ở slot
 * #option trong template).
 */
.p-multiselect-panel.report-filter-panel,
.p-multiselect-panel.pr-select-panel {
  width: max-content;
  max-width: min(22rem, 90vw);
}

/* panel PR: cap theo viewport height + chặn flip hẳn. PrimeVue absolute
   position panel: thiếu chỗ dưới (đã cuộn trang) thì flip top âm lên trên
   — đè ô "Ngày tạo PR". appendTo="self" cho panel absolute theo wrapper
   div.relative này, nên top 100% luôn ghim panel ngay dưới MultiSelect. */
.p-multiselect-panel.pr-select-panel {
  max-height: 38vh;
  overflow-y: auto;
  top: 100% !important;
}

.p-multiselect-panel.report-filter-panel .filter-option,
.p-multiselect-panel.pr-select-panel .filter-option {
  display: block;
  min-width: 0; /* flex item mặc định min-width:auto không co được */
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
</style>
