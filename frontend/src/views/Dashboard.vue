<script setup>
import { ref, computed, watch, onMounted, nextTick } from "vue";
import { FilterMatchMode } from "primevue/api";
import { useRouter } from "vue-router";
import { useToast } from "primevue/usetoast";
import { useAuth } from "@/service/AuthService";
import { useProject } from "@/service/ProjectService";
import { useLayout } from "@/layout/composables/layout";
import { apiFetch } from "@/service/ApiLoader";

const { isDarkTheme } = useLayout();
const router = useRouter();
const toast = useToast();
const { fullname, sessionExpired } = useAuth();
const { currentProject } = useProject();

// ---------- data ----------
const items = ref([]);
const loadingItems = ref(true);

// mọi khối dashboard (stat card, board, chart, bảng, thông báo) đều theo
// scope dropdown: All Project = toàn bộ, chọn sprint = chỉ sprint đó
const userStories = computed(() =>
  scopeItems.value.filter((it) => it.type === "User Story"),
);
const epics = computed(() => scopeItems.value.filter((it) => it.type === "Epic"));
const tasks = computed(() => scopeItems.value.filter((it) => it.type === "Task"));
const bugs = computed(() => scopeItems.value.filter((it) => it.type === "Bug"));
const byBoard = (list) =>
  Object.entries(
    list.value.reduce(
      (m, it) => ((m[it.board] = (m[it.board] || 0) + 1), m),
      {},
    ),
  ).sort((a, b) => b[1] - a[1]);
const userStoryByBoard = computed(() => byBoard(userStories));
const epicByBoard = computed(() => byBoard(epics));
const taskByBoard = computed(() => byBoard(tasks));
const bugByBoard = computed(() => byBoard(bugs));
const taskBase = ref("");
// scope đang xem: "" = All Project (toàn bộ items), ngược lại = 1 sprint
const selectedIteration = ref("");
const isAllProject = computed(() => !selectedIteration.value);
const sprintLabelOf = (it) => (it || "").split("\\").pop() || "—";
const iterationOptions = computed(() => [
  { label: "All Project", value: "" },
  ...[...new Set(items.value.map((i) => i.iteration).filter(Boolean))]
    .sort()
    .reverse()
    .map((it) => ({ label: sprintLabelOf(it), value: it })),
]);
const scopeItems = computed(() =>
  items.value
    .filter(
      (it) => !selectedIteration.value || it.iteration === selectedIteration.value,
    )
    // % theo setting (percent_mode) — backend /api/items trả it.percent
    .map((it) => ({ ...it, progress: it.percent ?? 0 })),
);
// ---------- filter table sprint ----------
// filter theo cột: ID (số bằng), Tiêu đề (chứa), Loại/Trạng thái (chọn nhiều),
// Tiến độ (số so sánh) — hiển thị dạng menu phễu trên header cột
// format constraints đầy đủ cho filterDisplay="menu" — form đơn giản
// {value, matchMode} crash khi đổi match mode (PrimeVue đọc .constraints[i])
const _menuFilter = (matchMode) => ({
  operator: "and",
  constraints: [{ value: null, matchMode }],
});
const dashFilters = ref({
  title: _menuFilter(FilterMatchMode.CONTAINS),
  type: _menuFilter(FilterMatchMode.IN),
  state: _menuFilter(FilterMatchMode.IN),
  progress: _menuFilter(FilterMatchMode.EQUALS),
});
const typeFilterOptions = computed(() =>
  [...new Set(scopeItems.value.map((i) => i.type))].sort(),
);
const stateFilterOptions = computed(() =>
  [...new Set(scopeItems.value.map((i) => i.state))].sort(),
);
const typeStyles = {
  Epic: { background: "#f97316", color: "#ffffff" },
  "User Story": { background: "#3b82f6", color: "#ffffff" },
  Task: { background: "#eab308", color: "#1f2937" },
  Bug: { background: "#ef4444", color: "#ffffff" },
};
// màu state lấy từ TFS qua /api/items (field stateColors), fallback xám
const stateStyles = ref({});
const textColorFor = (hex) => {
  const n = parseInt(hex.slice(1), 16);
  const [r, g, b] = [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  return 0.299 * r + 0.587 * g + 0.114 * b > 150 ? "#1f2937" : "#ffffff";
};
// tên scope hiển thị trên các tiêu đề khối
const scopeName = computed(() =>
  isAllProject.value ? "All Project" : sprintLabelOf(selectedIteration.value),
);
const typeIcons = {
  Epic: "pi-book",
  "User Story": "pi-inbox",
  Task: "pi-check-square",
  Bug: "pi-exclamation-triangle",
};
// SVG icon giống stat card, stroke trắng để đặt trên nền màu loại item
const SVG_ATTRS =
  'viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="1.1rem" height="1.1rem"';
const typeSvg = {
  Epic: `<svg ${SVG_ATTRS}><path d="M11.562 3.266a.5.5 0 0 1 .876 0L15.39 8.87a1 1 0 0 0 1.516.294L21.183 5.5a.5.5 0 0 1 .798.519l-2.834 10.246a1 1 0 0 1-.956.735H5.81a1 1 0 0 1-.957-.735L2.02 6.02a.5.5 0 0 1 .798-.519l4.276 3.664a1 1 0 0 0 1.516-.294z"/><path d="M5 21h14"/></svg>`,
  "User Story": `<svg ${SVG_ATTRS}><path d="M12 7v14"/><path d="M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z"/></svg>`,
  Task: `<svg ${SVG_ATTRS}><path d="m3 17 2 2 4-4"/><path d="m3 7 2 2 4-4"/><path d="M13 6h8"/><path d="M13 12h8"/><path d="M13 18h8"/></svg>`,
  Bug: `<svg ${SVG_ATTRS}><path d="m8 2 1.88 1.88"/><path d="M14.12 3.88 16 2"/><path d="M9 7.13v-1a3.003 3.003 0 1 1 6 0v1"/><path d="M12 20c-3.3 0-6-2.7-6-6v-3a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v3c0 3.3-2.7 6-6 6"/><path d="M12 20v-9"/><path d="M6.53 9C4.6 8.8 3 7.1 3 5"/><path d="M6 13H2"/><path d="M3 21c0-2.1 1.7-3.9 3.8-4"/><path d="M20.97 5c0 2.1-1.6 3.8-3.5 4"/><path d="M22 13h-4"/><path d="M17.2 17c2.1.1 3.8 1.9 3.8 4"/></svg>`,
};
// notifications kiểu dashboard-old: 6 sprint item đổi gần nhất, nhóm theo ngày thay đổi
const notifGroups = computed(() => {
  const today = new Date().toISOString().slice(0, 10);
  const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10);
  const groups = {};
  [...scopeItems.value]
    .sort((a, b) => (b.changed || "").localeCompare(a.changed || ""))
    .slice(0, 20)
    .forEach((it) => {
      const d = (it.changed || "").slice(0, 10);
      const label =
        d === today
          ? "Hôm nay"
          : d === yesterday
          ? "Hôm qua"
          : d.split("-").reverse().join("/");
      (groups[label] = groups[label] || []).push(it);
    });
  return Object.entries(groups).map(([label, list]) => ({ label, list }));
});
// dòng chữ chạy: thông tin notification của sprint — mỗi item 1 dòng riêng,
// chạy lần lượt (không gộp chung 1 chuỗi)
const sprintNotis = computed(() =>
  notifGroups.value.flatMap((g) =>
    g.list.map(
      (it) =>
        `${fmtDT(it.changed)} — ${it.type} #${it.id} "${it.title}" chuyển sang ${it.state}`,
    ),
  ),
);
// ---------- marquee: logo đầu chữ chạy phải sang trái; mỗi thông báo 1 dòng,
// dòng hiện tại chạy hết 50% thì dòng kế tiếp bắt đầu vào ----------
const marqueeTrack = ref(null);
let marqueeAnims = [];
const MARQUEE_SPEED = 0.06; // px/ms — tốc độ chữ chạy
const MARQUEE_GAP = 128; // px (8rem) — khoảng cách giữa 2 item kế tiếp

// các dòng đang chạy: mỗi dòng 1 span absolute trong track
const runners = ref([]);
const runnerEls = new Map();
const setRunnerEl = (key, el) =>
  el ? runnerEls.set(key, el) : runnerEls.delete(key);
let runnerSeq = 0;
let nextNoti = 0;
let spawnTimer = null;

const contentAt = (i) => {
  const list = sprintNotis.value;
  return list.length ? list[i % list.length] : "Chưa có thông báo";
};

// sinh 1 dòng: trôi từ ngoài mép phải đến hết mép trái,
// dòng kế tiếp vào sau khi hết dòng hiện tại đúng 8rem
function spawnRunner() {
  const key = ++runnerSeq;
  const content = contentAt(nextNoti);
  if (sprintNotis.value.length) nextNoti++;
  runners.value.push({ key, text: content });
  nextTick(() => {
    const el = runnerEls.get(key);
    const track = marqueeTrack.value;
    if (!el || !track) return;
    const W = track.clientWidth;
    const T = el.offsetWidth;
    if (!W || !T) return;
    const D = (W + T) / MARQUEE_SPEED; // tổng thời gian 1 dòng
    // translateY(-50%) giữ dòng giữa chiều cao track
    const run = el.animate(
      [
        { transform: `translate(${W}px, -50%)` },
        { transform: `translate(${-T}px, -50%)` },
      ],
      { duration: D, easing: "linear", fill: "forwards" },
    );
    marqueeAnims.push(run);
    // dòng sau vào khi đuôi dòng hiện tại cách mép phải đúng 8rem
    // (2 dòng cùng tốc độ nên gap giữ nguyên lúc chạy)
    spawnTimer = setTimeout(spawnRunner, (T + MARQUEE_GAP) / MARQUEE_SPEED);
    // hết màn hình: dọn span
    run.onfinish = () => {
      run.cancel();
      runners.value = runners.value.filter((r) => r.key !== key);
      marqueeAnims = marqueeAnims.filter((a) => a !== run);
    };
  });
}

function playMarquee() {
  marqueeAnims.forEach((a) => a.cancel());
  marqueeAnims = [];
  clearTimeout(spawnTimer);
  runners.value = [];
  runnerEls.clear();
  nextNoti = 0;
  nextTick(spawnRunner);
}

// đổi sprint / load lại data: chạy lại từ thông báo đầu tiên
watch(sprintNotis, () => playMarquee());

const fmtDT = (iso) => {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  const p = (n) => String(n).padStart(2, "0");
  return `${p(d.getDate())}/${p(d.getMonth() + 1)} ${p(d.getHours())}:${p(
    d.getMinutes(),
  )}`;
};
const sprintLineData = computed(() => {
  const byDate = {};
  scopeItems.value.forEach((it) => {
    const d = (it.changed || "—").slice(0, 10);
    byDate[d] = (byDate[d] || 0) + 1;
  });
  const labels = Object.keys(byDate).sort();
  let acc = 0;
  return {
    labels,
    datasets: [
      {
        label: "Thay đổi trong ngày",
        data: labels.map((l) => byDate[l]),
        fill: false,
        backgroundColor: "#2563eb",
        borderColor: "#2563eb",
        tension: 0.4,
      },
      {
        label: "Lũy tiến",
        data: labels.map((l) => (acc += byDate[l])),
        fill: false,
        backgroundColor: "#10b981",
        borderColor: "#10b981",
        tension: 0.4,
      },
    ],
  };
});
const sprintTypeProgress = computed(() => {
  const byType = {};
  scopeItems.value.forEach((it) => {
    (byType[it.type] = byType[it.type] || []).push(it.progress ?? 0);
  });
  return Object.entries(byType).map(([type, ps]) => ({
    type,
    count: ps.length,
    progress: Math.round(ps.reduce((a, b) => a + b, 0) / ps.length),
  }));
});

// ---------- load ----------
onMounted(async () => {
  // chạy marquee sau khi render, restart khi đổi kích thước
  nextTick(playMarquee);
  const track = marqueeTrack.value;
  if (track && "ResizeObserver" in window) {
    new ResizeObserver(() => playMarquee()).observe(track);
  }
  try {
    const r = await apiFetch("/api/items");
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
});

// ---------- charts ----------
const chartOptions = ref(null);
const applyLightTheme = () => {
  const scales = {
    x: { ticks: { color: "#495057" }, grid: { color: "#ebedef" } },
    y: { ticks: { color: "#495057" }, grid: { color: "#ebedef" } },
  };
  chartOptions.value = {
    plugins: { legend: { labels: { color: "#495057" } } },
    scales,
  };
};
const applyDarkTheme = () => {
  const scales = {
    x: {
      ticks: { color: "#ebedef" },
      grid: { color: "rgba(160, 167, 181, .3)" },
    },
    y: {
      ticks: { color: "#ebedef" },
      grid: { color: "rgba(160, 167, 181, .3)" },
    },
  };
  chartOptions.value = {
    plugins: { legend: { labels: { color: "#ebedef" } } },
    scales,
  };
};
watch(
  isDarkTheme,
  (val) => {
    val ? applyDarkTheme() : applyLightTheme();
  },
  { immediate: true },
);
</script>

<template>
  <div class="grid">
    <!-- sprint switcher: chữ chạy giới thiệu sprint + dropdown -->
    <div class="col-12 p-0 px-3 flex align-items-center gap-2">
      <img
        src="/layout/images/pinia-course.png"
        alt=""
        class="flex-shrink-0"
        style="height: 2.5rem"
      />
      <div class="sprint-marquee text-500">
        <div ref="marqueeTrack" class="sprint-marquee-track">
          <span
            v-for="r in runners"
            :key="r.key"
            :ref="(el) => setRunnerEl(r.key, el)"
            class="sprint-marquee-text"
          >
            <div
              class="sprint-marquee-logo"
              :style="{
                backgroundImage: `url(/layout/images/${
                  isDarkTheme ? 'logo-light' : 'logo-dark'
                }.svg)`,
              }"
            ></div>
            <span class="">{{ r.text }}</span>
          </span>
        </div>
      </div>
      <Dropdown
        v-model="selectedIteration"
        :options="iterationOptions"
        optionLabel="label"
        optionValue="value"
        placeholder="All Project"
        :disabled="loadingItems"
        style="width: 14rem"
      />
    </div>
    <!-- stat cards -->
    <div class="col-12 lg:col-6 xl:col-3">
      <div class="card mb-0 h-full">
        <div class="flex justify-content-between mb-3">
          <div>
            <span class="block text-500 font-medium mb-3">Epic</span>
            <div class="text-900 font-medium text-xl">{{ epics.length }}</div>
          </div>
          <div
            class="flex align-items-center justify-content-center bg-orange-100 border-round"
            style="width: 2.5rem; height: 2.5rem"
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
              width="1.25rem"
              height="1.25rem"
              class="text-orange-500"
            >
              <path
                d="M11.562 3.266a.5.5 0 0 1 .876 0L15.39 8.87a1 1 0 0 0 1.516.294L21.183 5.5a.5.5 0 0 1 .798.519l-2.834 10.246a1 1 0 0 1-.956.735H5.81a1 1 0 0 1-.957-.735L2.02 6.02a.5.5 0 0 1 .798-.519l4.276 3.664a1 1 0 0 0 1.516-.294z"
              />
              <path d="M5 21h14" />
            </svg>
          </div>
        </div>
        <div
          class="flex flex-wrap text-sm"
          style="column-gap: 0.75rem; row-gap: 0.1rem"
        >
          <div
            v-for="[board, n] in epicByBoard"
            :key="board"
            class="flex align-items-center min-w-0"
            style="width: calc(50% - 0.375rem)"
          >
            <span
              class="text-500 white-space-nowrap overflow-hidden text-overflow-ellipsis min-w-0 mr-1"
              >{{ board }}</span
            >
            <span class="text-900 font-medium flex-shrink-0">{{ n }}</span>
          </div>
        </div>
      </div>
    </div>
    <div class="col-12 lg:col-6 xl:col-3">
      <div class="card mb-0 h-full">
        <div class="flex justify-content-between mb-3">
          <div>
            <span class="block text-500 font-medium mb-3">User Story</span>
            <div class="text-900 font-medium text-xl">
              {{ userStories.length }}
            </div>
          </div>
          <div
            class="flex align-items-center justify-content-center bg-blue-100 border-round"
            style="width: 2.5rem; height: 2.5rem"
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
              width="1.25rem"
              height="1.25rem"
              class="text-blue-500"
            >
              <path d="M12 7v14" />
              <path
                d="M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z"
              />
            </svg>
          </div>
        </div>
        <div
          class="flex flex-wrap text-sm"
          style="column-gap: 0.75rem; row-gap: 0.1rem"
        >
          <div
            v-for="[board, n] in userStoryByBoard"
            :key="board"
            class="flex align-items-center min-w-0"
            style="width: calc(50% - 0.375rem)"
          >
            <span
              class="text-500 white-space-nowrap overflow-hidden text-overflow-ellipsis min-w-0 mr-1"
              >{{ board }}</span
            >
            <span class="text-900 font-medium flex-shrink-0">{{ n }}</span>
          </div>
        </div>
      </div>
    </div>
    <div class="col-12 lg:col-6 xl:col-3">
      <div class="card mb-0 h-full">
        <div class="flex justify-content-between mb-3">
          <div>
            <span class="block text-500 font-medium mb-3">Task</span>
            <div class="text-900 font-medium text-xl">{{ tasks.length }}</div>
          </div>
          <div
            class="flex align-items-center justify-content-center bg-yellow-100 border-round"
            style="width: 2.5rem; height: 2.5rem"
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
              width="1.25rem"
              height="1.25rem"
              class="text-yellow-500"
            >
              <path d="m3 17 2 2 4-4" />
              <path d="m3 7 2 2 4-4" />
              <path d="M13 6h8" />
              <path d="M13 12h8" />
              <path d="M13 18h8" />
            </svg>
          </div>
        </div>
        <div
          class="flex flex-wrap text-sm"
          style="column-gap: 0.75rem; row-gap: 0.1rem"
        >
          <div
            v-for="[board, n] in taskByBoard"
            :key="board"
            class="flex align-items-center min-w-0"
            style="width: calc(50% - 0.375rem)"
          >
            <span
              class="text-500 white-space-nowrap overflow-hidden text-overflow-ellipsis min-w-0 mr-1"
              >{{ board }}</span
            >
            <span class="text-900 font-medium flex-shrink-0">{{ n }}</span>
          </div>
        </div>
      </div>
    </div>
    <div class="col-12 lg:col-6 xl:col-3">
      <div class="card mb-0 h-full">
        <div class="flex justify-content-between mb-3">
          <div>
            <span class="block text-500 font-medium mb-3">Bug</span>
            <div class="text-900 font-medium text-xl">{{ bugs.length }}</div>
          </div>
          <div
            class="flex align-items-center justify-content-center bg-red-100 border-round"
            style="width: 2.5rem; height: 2.5rem"
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
              width="1.25rem"
              height="1.25rem"
              class="text-red-500"
            >
              <path d="m8 2 1.88 1.88" />
              <path d="M14.12 3.88 16 2" />
              <path d="M9 7.13v-1a3.003 3.003 0 1 1 6 0v1" />
              <path
                d="M12 20c-3.3 0-6-2.7-6-6v-3a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v3c0 3.3-2.7 6-6 6"
              />
              <path d="M12 20v-9" />
              <path d="M6.53 9C4.6 8.8 3 7.1 3 5" />
              <path d="M6 13H2" />
              <path d="M3 21c0-2.1 1.7-3.9 3.8-4" />
              <path d="M20.97 5c0 2.1-1.6 3.8-3.5 4" />
              <path d="M22 13h-4" />
              <path d="M17.2 17c2.1.1 3.8 1.9 3.8 4" />
            </svg>
          </div>
        </div>
        <div
          class="flex flex-wrap text-sm"
          style="column-gap: 0.75rem; row-gap: 0.1rem"
        >
          <div
            v-for="[board, n] in bugByBoard"
            :key="board"
            class="flex align-items-center min-w-0"
            style="width: calc(50% - 0.375rem)"
          >
            <span
              class="text-500 white-space-nowrap overflow-hidden text-overflow-ellipsis min-w-0 mr-1"
              >{{ board }}</span
            >
            <span class="text-900 font-medium flex-shrink-0">{{ n }}</span>
          </div>
        </div>
      </div>
    </div>
    <!-- progress -->
    <div class="col-12 xl:col-6">
      <div class="card h-full">
        <h5>Tiến độ work items — {{ scopeName }}</h5>
        <ul class="list-none p-0 m-0">
          <li
            v-for="t in sprintTypeProgress"
            :key="t.type"
            class="flex flex-column md:flex-row md:align-items-center md:justify-content-between mb-4"
          >
            <div>
              <span class="text-900 font-medium mr-2 mb-1 md:mb-0">{{
                t.type
              }}</span>
              <div class="mt-1 text-500 text-sm">{{ t.count }} items</div>
            </div>
            <div class="mt-2 md:mt-0 flex align-items-center">
              <div
                class="surface-300 border-round overflow-hidden w-10rem lg:w-6rem"
                style="height: 8px"
              >
                <div
                  class="h-full"
                  :style="{
                    width: t.progress + '%',
                    background: typeStyles[t.type]?.background,
                  }"
                ></div>
              </div>
              <span class="ml-3 font-medium w-3rem text-right"
                >{{ t.progress }}%</span
              >
            </div>
          </li>
        </ul>
      </div>
    </div>
    <!-- sprint overview (line) -->
    <div class="col-12 xl:col-6">
      <div class="card h-full">
        <h5>Tổng quan — {{ scopeName }}</h5>
        <Chart type="line" :data="sprintLineData" :options="chartOptions" />
      </div>
    </div>
    <!-- sprint items table (2 phần) + notifications (1 phần) -->
    <div class="col-12 xl:col-8">
      <div class="card">
        <h5>Items — {{ scopeName }}</h5>
        <DataTable
          :value="scopeItems"
          :rows="5"
          :paginator="true"
          :rowsPerPageOptions="[5, 10, 20, 50]"
          v-model:filters="dashFilters"
          filterDisplay="menu"
          responsiveLayout="scroll"
        >
          <template #empty>
            <div
              class="flex flex-column align-items-center justify-content-center py-5 text-500"
            >
              <i class="pi pi-inbox text-4xl mb-2"></i>
              <span>Không có item nào</span>
            </div>
          </template>
          <Column
            field="id"
            header="ID"
            :sortable="true"
            style="width: 7%"
          ></Column>
          <Column
            field="title"
            header="Tiêu đề"
            :sortable="true"
            :filter="true"
            style="width: 23%"
          >
            <template #body="slotProps">
              <span class="one-line" v-tooltip.bottom="slotProps.data.title">{{
                slotProps.data.title
              }}</span>
            </template>
            <template #filter="{ filterModel, filterCallback }">
              <InputText
                v-model="filterModel.value"
                @keydown.enter="filterCallback()"
                class="p-column-filter"
                placeholder="Tìm tiêu đề" />
            </template>
          </Column>
          <Column
            field="type"
            header="Loại"
            :sortable="true"
            :filter="true"
            :showFilterMatchModes="false"
            :filterMenuStyle="{ width: '14rem' }"
            style="width: 13%"
          >
            <template #body="slotProps">
              <Tag
                :value="slotProps.data.type"
                :style="typeStyles[slotProps.data.type]"
              />
            </template>
            <template #filter="{ filterModel }">
              <MultiSelect
                v-model="filterModel.value"
                :options="typeFilterOptions"
                placeholder="Chọn loại"
                class="p-column-filter"
                :showClear="true"
                :maxSelectedLabels="4"
              />
            </template>
          </Column>
          <Column
            field="state"
            header="Trạng thái"
            :sortable="true"
            :filter="true"
            :showFilterMatchModes="false"
            :filterMenuStyle="{ width: '14rem' }"
            style="width: 16%"
          >
            <template #body="slotProps">
              <Tag
                :value="slotProps.data.state"
                :style="
                  stateStyles[slotProps.data.state] || {
                    background: '#b2b2b2',
                    color: '#1f2937',
                  }
                "
              />
            </template>
            <template #filter="{ filterModel }">
              <MultiSelect
                v-model="filterModel.value"
                :options="stateFilterOptions"
                placeholder="Chọn trạng thái"
                class="p-column-filter"
                :showClear="true"
                :maxSelectedLabels="4"
              />
            </template>
          </Column>
          <Column
            field="progress"
            header="Tiến độ"
            :sortable="true"
            :filter="true"
            dataType="numeric"
            style="width: 16%"
          >
            <template #body="slotProps">
              <div class="flex align-items-center">
                <ProgressBar
                  :value="slotProps.data.progress"
                  :showValue="false"
                  style="height: 8px; width: 4rem"
                />
                <span class="ml-2 font-medium w-3rem text-right"
                  >{{ slotProps.data.progress }}%</span
                >
              </div>
            </template>
            <template #filter="{ filterModel, filterCallback }">
              <InputText
                v-model="filterModel.value"
                @keydown.enter="filterCallback()"
                class="p-column-filter"
                placeholder="%" />
            </template>
          </Column>
          <Column style="width: 6%">
            <template #header> Xem </template>
            <template #body="slotProps">
              <a
                :href="taskBase + slotProps.data.id"
                target="_blank"
                rel="noopener"
              >
                <Button
                  icon="pi pi-search"
                  type="button"
                  class="p-button-text"
                ></Button>
              </a>
            </template>
          </Column>
        </DataTable>
      </div>
    </div>
    <!-- notifications -->
    <div class="col-12 xl:col-4">
      <div class="card flex flex-column h-full noti-card">
        <h5>Notifications</h5>
        <div class="overflow-y-auto flex-1" style="min-height: 0">
          <template v-for="group in notifGroups" :key="group.label">
            <span class="block text-600 font-medium mb-3">{{
              group.label.toUpperCase()
            }}</span>
            <ul class="p-0 mx-0 mt-0 mb-3 list-none">
              <li
                v-for="it in group.list"
                :key="it.id"
                class="flex align-items-center py-2 border-bottom-1 surface-border"
              >
                <div
                  class="w-3rem h-3rem flex align-items-center justify-content-center border-circle mr-3 flex-shrink-0"
                  :style="{
                    background:
                      (typeStyles[it.type] || {}).background || '#94a3b8',
                  }"
                >
                  <span v-html="typeSvg[it.type] || typeSvg.Task"></span>
                </div>
                <div class="text-900 line-height-3 flex-1">
                  {{ it.title }}
                  <div class="mt-1 flex align-items-center flex-wrap row-gap-1">
                    <span class="text-700 text-sm mr-2 white-space-nowrap"
                      >chuyển sang</span
                    >
                    <span
                      class="text-sm font-medium"
                      :style="{
                        color:
                          (stateStyles[it.state] || {}).background || '#6b7280',
                      }"
                      >{{ it.state }}</span
                    >
                    <span class="text-500 text-sm ml-2 white-space-nowrap">{{
                      fmtDT(it.changed)
                    }}</span>
                  </div>
                </div>
              </li>
            </ul>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* dòng chữ chạy giới thiệu sprint */
.sprint-marquee {
  flex: 1 1 0;
  min-width: 0;
}

.sprint-marquee-track {
  position: relative;
  flex: 1 1 0;
  min-width: 0;
  height: 2rem; /* track rỗng (span absolute) — height cố định theo logo */
  overflow: hidden;
  white-space: nowrap;
  /* mờ dần ở 2 mép: trái 3rem, phải 0.5rem */
  -webkit-mask-image: linear-gradient(
    to right,
    transparent 0,
    black 3rem,
    black calc(100% - 0.5rem),
    transparent 100%
  );
  mask-image: linear-gradient(
    to right,
    transparent 0,
    black 3rem,
    black calc(100% - 0.5rem),
    transparent 100%
  );
}

.sprint-marquee-text {
  position: absolute;
  left: 0;
  top: 50%;
  display: inline-flex;
  align-items: center;
  white-space: nowrap;
  transform: translateY(-50%); /* giữ giữa chiều cao, transform X do WAAPI */
}

/* logo đầu chữ: div bọc fixed-size, img bên trong fill kín 100% cả 2 chiều */
.sprint-marquee-logo {
  display: inline-block;
  width: 2rem;
  height: 2rem;
  vertical-align: middle;
  background-repeat: no-repeat;
  background-size: 100% 100%;
  transform: rotate(12deg);
}

/* tiêu đề table: 1 dòng, dài quá thì ... */
.one-line {
  display: block;
  max-width: 100%;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

/* table-layout fixed để width % của cột được giữ, ellipsis mới hoạt động */
:deep(.p-datatable-table) {
  table-layout: fixed;
}

/* header không rớt dòng */
:deep(.p-datatable-thead > tr > th) {
  white-space: nowrap;
}

/* Tag Trạng thái/Loại: 1 dòng */
:deep(.p-tag) {
  white-space: nowrap;
}

/* noti card: không cao quá 50vh màn hình; padding dồn vào inner
   để scrollbar sát biên phải card */
.noti-card {
  max-height: 50vh;
  padding: 0;
  overflow: hidden;
}

.noti-card > h5 {
  margin: 0;
  padding: 1.5rem 2rem 1rem;
}

.noti-card > .overflow-y-auto {
  padding: 0 2rem 1.5rem;
  scrollbar-width: none; /* Firefox: ẩn scrollbar */
}

.noti-card > .overflow-y-auto::-webkit-scrollbar {
  width: 0;
  background: transparent;
}

/* hover vào card mới hiện scrollbar */
.noti-card:hover > .overflow-y-auto {
  scrollbar-width: thin;
}

.noti-card:hover > .overflow-y-auto::-webkit-scrollbar {
  width: 0.5rem;
}

.noti-card:hover > .overflow-y-auto::-webkit-scrollbar-thumb {
  background: var(--surface-300);
  border-radius: 6px;
}

.noti-card:hover > .overflow-y-auto::-webkit-scrollbar-thumb:hover {
  background: var(--surface-400);
}
</style>
