<script setup>
import { reactive, ref, computed, watch, onMounted } from "vue";
import { useRouter } from "vue-router";
import { useToast } from "primevue/usetoast";
import { useAuth } from "@/service/AuthService";
import { useProject } from "@/service/ProjectService";

const router = useRouter();
const toast = useToast();
const { fullname, sessionExpired } = useAuth();
const { currentProject } = useProject();

// ---------- data ----------
const items = ref([]);
const loadingItems = ref(true);
const search = ref("");
const filterState = ref([]);
const filterIteration = ref([]);
const filterType = ref([]);
const filterParent = ref([]);
const picked = reactive({ today: new Set(), next: new Set() });
const reportDate = ref(new Date());
const previewTab = ref(0);
const resultDialog = ref(false);
const resultTab = ref(2);
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
const stateProgress = { New: 10, Active: 40, Resolved: 70, Closed: 100 };
const progressOf = (it) => stateProgress[it.state] ?? 30;

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
const visibleItems = computed(() => {
  const q = search.value.toLowerCase().trim();
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
      (!q || String(it.id) === q || it.title.toLowerCase().includes(q)),
  );
});
// sort theo iteration để row group hoạt động
const groupedItems = computed(() =>
  [...visibleItems.value].sort((a, b) =>
    (b.iteration || "").localeCompare(a.iteration || ""),
  ),
);
const sprintLabel = (it) =>
  (it || "").split("\\").pop() || "Không thuộc sprint";

// ---------- load ----------
onMounted(async () => {
  reportDate.value = new Date();
  try {
    const r = await fetch("/api/items");
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
  const who = fullname.value || "...";
  const lines = [
    `*Báo cáo nhân sự* ${dateStr}`,
    `*Nhân sự:* ${who}`,
    "*Công việc:*",
  ];
  for (const it of todayItems.value)
    lines.push(`- ${escapeMd(it.type)} ${it.id}: ${escapeMd(it.title)} (100%)`);
  if (!todayItems.value.length) lines.push("- ...");
  lines.push("*Công việc ngày tiếp theo:*");
  for (const it of nextItems.value)
    lines.push(`- ${escapeMd(it.type)} ${it.id}: ${escapeMd(it.title)}`);
  if (!nextItems.value.length) lines.push("- ...");
  lines.push("*Vấn đề:*", "- None");
  return lines.join("\n");
});

const larkMd = computed(() => {
  const dateStr = ddMMyyyy(reportDate.value);
  const merged = [];
  const seen = new Set();
  for (const it of [...todayItems.value, ...nextItems.value]) {
    if (!seen.has(it.id)) {
      seen.add(it.id);
      merged.push(it);
    }
  }
  const lines = [
    "| Status | Start date | End date | Note | Type | Task ID | Task Name | Task Link |",
    "| --- | --- | --- | --- | --- | --- | --- | --- |",
  ];
  for (const it of merged) {
    const link = taskBase.value ? `${taskBase.value}${it.id}` : `${it.id}`;
    lines.push(
      `| ${escapeMd(it.state)} | ${dateStr} |  |  | ${escapeMd(
        it.type,
      )} | ${it.id} | ${escapeMd(it.title)} | ${link} |`,
    );
  }
  return lines.join("\n");
});

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
// reset cả 3 tab
const resetAll = () => [0, 1, 2].forEach((t) => (dirty[t] = false));

// ---------- report ----------
// nội dung report theo tab, giữ edit tay của người dùng nếu có
const reportOf = (t) => (dirty[t] ? edited[t] : baseOf(t));

function makeReport() {
  if (!picked.today.size && !picked.next.size) {
    toast.add({
      severity: "warn",
      summary: "Chưa chọn item",
      detail: "Chọn ít nhất 1 item (cột Hôm nay hoặc Mai)",
      life: 4000,
    });
    return;
  }
  resultTab.value = 2;
  resultDialog.value = true;
}

const resultText = computed(() => reportOf(resultTab.value));

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
        <div class="flex justify-content-between align-items-center mb-4">
          <h5 class="m-0">
            Chọn công việc <Tag v-if="currentProject" :value="currentProject" />
          </h5>
        </div>
        <div class="mb-3">
          <IconField iconPosition="left" class="w-full">
            <InputIcon class="pi pi-search" />
            <InputText
              v-model="search"
              placeholder="Tìm theo ID hoặc tiêu đề..."
              class="w-full"
            />
          </IconField>
        </div>
        <div class="flex gap-2 mb-3">
          <MultiSelect
            v-model="filterState"
            :options="stateOptions"
            placeholder="Mọi State"
            :filter="true"
            class="flex-1 min-w-0"
          />
          <MultiSelect
            v-model="filterIteration"
            :options="iterationOptions"
            optionLabel="label"
            optionValue="value"
            placeholder="Mọi sprint"
            :filter="true"
            class="flex-1 min-w-0"
          />
          <MultiSelect
            v-model="filterType"
            :options="typeOptions"
            placeholder="Mọi loại"
            :filter="true"
            class="flex-1 min-w-0"
          />
          <MultiSelect
            v-model="filterParent"
            :options="parentOptions"
            optionLabel="label"
            optionValue="value"
            placeholder="Mọi parent"
            :filter="true"
            class="flex-1 min-w-0"
          />
        </div>
        <div
          class="flex flex-wrap gap-2 mb-4 align-items-center justify-content-end"
        >
          <Button
            label="Chọn tất cả (cũ)"
            class="p-button-outlined p-button-sm"
            @click="toggleAll('today')"
          />
          <Button
            label="Chọn tất cả (mới)"
            class="p-button-outlined p-button-sm"
            @click="toggleAll('next')"
          />
          <Button
            label="Clear"
            icon="pi pi-trash"
            class="p-button-outlined p-button-danger p-button-sm"
            @click="clearPick"
          />
        </div>
        <DataTable
          :value="groupedItems"
          rowGroupMode="subheader"
          groupRowsBy="iteration"
          :pt="{ rowGroupHeaderCell: { colspan: 5 } }"
          :loading="loadingItems"
          :rows="rows"
          :rowsPerPageOptions="[10, 20, 50, 100]"
          @page="onPage"
          :paginator="true"
          dataKey="id"
          responsiveLayout="scroll"
          :rowClass="rowClass"
          currentPageReportTemplate="Hiện {first}-{last} / {totalRecords}"
          paginatorTemplate="FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink RowsPerPageDropdown CurrentPageReport"
        >
          <template #empty>
            <div
              class="flex flex-column align-items-center justify-content-center py-5 text-500"
            >
              <i class="pi pi-inbox text-4xl mb-2"></i>
              <span>Không có dữ liệu</span>
            </div>
          </template>
          <template #groupheader="slotProps">
            <span class="font-bold text-primary">{{
              sprintLabel(slotProps.data.iteration)
            }}</span>
            <span class="text-500 font-normal ml-2"
              >({{
                groupedItems.filter(
                  (i) => i.iteration === slotProps.data.iteration,
                ).length
              }}
              items)</span
            >
          </template>
          <Column field="id" header="ID" :sortable="true" style="width: 10%">
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
            style="width: 44%"
          >
            <template #body="slotProps">
              <span class="one-line" v-tooltip.bottom="slotProps.data.title">{{
                slotProps.data.title
              }}</span>
              <div
                class="flex align-items-center flex-wrap mt-1"
                style="column-gap: 0.5rem"
              >
                <span
                  class="text-sm font-medium"
                  :style="{
                    color: typeColors[slotProps.data.type] || '#6b7280',
                  }"
                  >{{ slotProps.data.type }}</span
                >
                <ProgressBar
                  :value="progressOf(slotProps.data)"
                  :showValue="false"
                  style="height: 8px; width: 4rem"
                />
                <span class="font-medium text-sm w-2rem"
                  >{{ progressOf(slotProps.data) }}%</span
                >
              </div>
            </template>
          </Column>
          <Column
            field="state"
            header="Trạng thái"
            :sortable="true"
            style="width: 18%"
          >
            <template #body="slotProps">
              <Tag
                :value="slotProps.data.state"
                class="white-space-nowrap"
                :style="
                  stateStyles[slotProps.data.state] || {
                    background: '#b2b2b2',
                    color: '#1f2937',
                  }
                "
              />
            </template>
          </Column>
          <Column style="width: 14%">
            <template #header>
              <div class="flex align-items-center gap-2">
                <Checkbox
                  :modelValue="allPicked('next')"
                  binary
                  @update:modelValue="toggleAll('next')"
                />
                <span>Mới</span>
              </div>
            </template>
            <template #body="slotProps">
              <Checkbox
                :modelValue="picked.next.has(slotProps.data.id)"
                binary
                @update:modelValue="toggle(slotProps.data.id, 'next')"
              />
            </template>
          </Column>
          <Column style="width: 14%">
            <template #header>
              <div class="flex align-items-center gap-2">
                <Checkbox
                  :modelValue="allPicked('today')"
                  binary
                  @update:modelValue="toggleAll('today')"
                />
                <span>Cũ</span>
              </div>
            </template>
            <template #body="slotProps">
              <Checkbox
                :modelValue="picked.today.has(slotProps.data.id)"
                binary
                @update:modelValue="toggle(slotProps.data.id, 'today')"
              />
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
          />
          <Button
            label="Tạo report"
            icon="pi pi-file"
            @click="makeReport"
          />
        </div>

        <div class="relative">
          <TabView v-model:activeIndex="previewTab">
            <TabPanel header="Chat">
              <div class="flex justify-content-end gap-1 mb-2">
                <Button
                  icon="pi pi-refresh"
                  class="p-button-text p-button-sm"
                  aria-label="Reset về nội dung tự động"
                  @click="resetTab"
                />
                <Button
                  icon="pi pi-copy"
                  class="p-button-text p-button-sm"
                  aria-label="Copy"
                  @click="copyText(tabText)"
                />
              </div>
              <textarea
                v-model="tabText"
                class="preview-input"
                wrap="off"
                spellcheck="false"
              ></textarea>
            </TabPanel>
            <TabPanel header="Lark">
              <div class="flex justify-content-end gap-1 mb-2">
                <Button
                  icon="pi pi-refresh"
                  class="p-button-text p-button-sm"
                  aria-label="Reset về nội dung tự động"
                  @click="resetTab"
                />
                <Button
                  icon="pi pi-copy"
                  class="p-button-text p-button-sm"
                  aria-label="Copy"
                  @click="copyText(tabText)"
                />
              </div>
              <textarea
                v-model="tabText"
                class="preview-input"
                wrap="off"
                spellcheck="false"
              ></textarea>
            </TabPanel>
            <TabPanel header="Full">
              <div class="flex justify-content-end gap-1 mb-2">
                <Button
                  icon="pi pi-refresh"
                  class="p-button-text p-button-sm"
                  aria-label="Reset về nội dung tự động"
                  @click="resetTab"
                />
                <Button
                  icon="pi pi-copy"
                  class="p-button-text p-button-sm"
                  aria-label="Copy"
                  @click="copyText(tabText)"
                />
              </div>
              <textarea
                v-model="tabText"
                class="preview-input"
                wrap="off"
                spellcheck="false"
              ></textarea>
            </TabPanel>
          </TabView>
          <Button
            icon="pi pi-refresh"
            class="p-button-outlined p-button-sm reset-all-btn"
            v-tooltip.bottom="'Reset preview cả 3 tab'"
            @click="resetAll"
          />
        </div>
      </div>
    </div>

    <!-- result dialog: full screen, xem trước + tải file -->
    <Dialog
      v-model:visible="resultDialog"
      modal
      header="Xem trước report"
      class="report-fullscreen"
      :style="{ width: '100vw', height: '100vh' }"
      :contentStyle="{ height: 'calc(100vh - 8rem)', overflow: 'auto' }"
    >
      <TabView v-model:activeIndex="resultTab">
        <TabPanel header="Chat">
          <pre class="report-pre m-0">{{ reportOf(0) }}</pre>
        </TabPanel>
        <TabPanel header="Lark">
          <pre class="report-pre m-0">{{ reportOf(1) }}</pre>
        </TabPanel>
        <TabPanel header="Full">
          <pre class="report-pre m-0">{{ reportOf(2) }}</pre>
        </TabPanel>
      </TabView>
      <template #footer>
        <Button
          label="Copy"
          icon="pi pi-copy"
          class="p-button-outlined"
          @click="copyText(resultText)"
        />
        <Button
          :label="`Tải file (${reportFileName()})`"
          icon="pi pi-download"
          @click="downloadReport"
        />
        <Button
          label="Đóng"
          class="p-button-text"
          @click="resultDialog = false"
        />
      </template>
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

/* table-layout fixed để width % của cột được giữ, ellipsis mới hoạt động */
:deep(.p-datatable-table) {
  table-layout: fixed;
}

/* row group header: band full-width cho rõ nhóm sprint
   PrimeVue render td colspan = số cột - 1, nên style trên tr để phủ hết hàng */
:deep(.p-rowgroup-header) {
  background: var(--surface-ground);
  box-shadow: inset 0 -1px 0 var(--surface-border);
}
:deep(.p-rowgroup-header td) {
  background: transparent;
}

/* vùng sửa preview: giống pre cũ, cao theo viewport */
.preview-input {
  display: block;
  width: 100%;
  height: calc(100vh - 28rem);
  margin: 0;
  padding: 0.75rem;
  border: none;
  outline: none;
  border-radius: 6px;
  resize: none;
  overflow: auto;
  white-space: pre; /* không rớt dòng, cuộn ngang */
  background: #111827;
  color: #f3f4f6;
  font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas,
    monospace;
  font-size: 0.875rem;
  line-height: 1.5;
}

/* tab cách đường border-bottom của nav */
:deep(.p-tabview .p-tabview-nav li a),
:deep(.p-tabview .p-tabview-nav li) {
  padding-bottom: 1.25rem !important;
}

/* nút reset-all nằm trong hàng tab, dạt phải */
.reset-all-btn {
  position: absolute;
  top: 0.3rem;
  right: 0;
}

/* chừa chỗ bên phải nav để nút reset-all không đè lên tab cuối */
:deep(.p-tabview-nav) {
  padding-right: 3rem;
  border-top-right-radius: 6px;
  border-bottom-right-radius: 6px;
}

/* header không rớt dòng */
:deep(.p-datatable-thead > tr > th) {
  white-space: nowrap;
}

/* Tag Trạng thái: 1 dòng */
:deep(.p-tag) {
  white-space: nowrap;
}

/* dialog report full màn hình: tắt căn giữa mặc định của p-dialog */
:deep(.report-fullscreen.p-dialog) {
  position: fixed;
  inset: 0;
  width: 100vw;
  height: 100vh;
  max-width: none;
  max-height: none;
  margin: 0;
  transform: none !important;
}

/* nội dung report trong dialog */
.report-pre {
  padding: 0.75rem;
  border-radius: 6px;
  background: #111827;
  color: #f3f4f6;
  font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas,
    monospace;
  font-size: 0.875rem;
  line-height: 1.5;
  white-space: pre;
  overflow: auto;
}
</style>
