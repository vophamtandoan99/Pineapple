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
// sort theo iteration để item cùng sprint đứng cạnh nhau
const groupedItems = computed(() =>
  [...visibleItems.value].sort((a, b) =>
    (b.iteration || "").localeCompare(a.iteration || ""),
  ),
);
const sprintLabel = (it) =>
  (it || "").split("\\").pop() || "Không thuộc sprint";
// option filter có khi là string (state/type), có khi object {label, value}
const optionLabelOf = (o) => (typeof o === "string" ? o : o.label);

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
      `| ${escapeMd(it.state)} | ${dateStr} |  |  | ${escapeMd(it.type)} | ${
        it.id
      } | ${escapeMd(it.title)} | ${link} |`,
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
      summary: "Chưa chọn item",
      detail: "Chọn ít nhất 1 item (cột Hôm nay hoặc Mai)",
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
        <div class="flex justify-content-between align-items-center mb-4">
          <h5 class="m-0 flex align-items-center">
            Chọn công việc
            <Tag v-if="currentProject" :value="currentProject" class="ml-2" />
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
            panelClass="report-filter-panel"
          >
            <template #option="s">
              <span
                class="filter-option"
                v-tooltip.bottom="optionLabelOf(s.option)"
                >{{ optionLabelOf(s.option) }}</span
              >
            </template>
          </MultiSelect>
          <MultiSelect
            v-model="filterIteration"
            :options="iterationOptions"
            optionLabel="label"
            optionValue="value"
            placeholder="Mọi sprint"
            :filter="true"
            class="flex-1 min-w-0"
            panelClass="report-filter-panel"
          >
            <template #option="s">
              <span
                class="filter-option"
                v-tooltip.bottom="optionLabelOf(s.option)"
                >{{ optionLabelOf(s.option) }}</span
              >
            </template>
          </MultiSelect>
          <MultiSelect
            v-model="filterType"
            :options="typeOptions"
            placeholder="Mọi loại"
            :filter="true"
            class="flex-1 min-w-0"
            panelClass="report-filter-panel"
          >
            <template #option="s">
              <span
                class="filter-option"
                v-tooltip.bottom="optionLabelOf(s.option)"
                >{{ optionLabelOf(s.option) }}</span
              >
            </template>
          </MultiSelect>
          <MultiSelect
            v-model="filterParent"
            :options="parentOptions"
            optionLabel="label"
            optionValue="value"
            placeholder="Mọi parent"
            :filter="true"
            class="flex-1 min-w-0"
            panelClass="report-filter-panel"
          >
            <template #option="s">
              <span
                class="filter-option"
                v-tooltip.bottom="optionLabelOf(s.option)"
                >{{ optionLabelOf(s.option) }}</span
              >
            </template>
          </MultiSelect>
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
          :loading="loadingItems"
          :rows="rows"
          scrollable
          scrollHeight="51vh"
          :rowsPerPageOptions="[5, 10, 20, 50, 100]"
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
          <Column
            field="id"
            header="ID"
            :sortable="true"
            style="width: 5rem"
            frozen
          >
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
            style="width: 40%"
          >
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
                style="column-gap: 0.5rem"
              >
                <ProgressBar
                  :value="progressOf(slotProps.data)"
                  :showValue="false"
                  style="height: 4px; width: 8rem"
                />
                <span class="italic text-500 text-sm w-2rem"
                  >{{ progressOf(slotProps.data) }}%</span
                >
              </div>
            </template>
          </Column>
          <Column
            field="state"
            header="Trạng thái"
            :sortable="true"
            style="min-width: 15rem"
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
          <Column style="min-width: 5rem" frozen alignFrozen="right">
            <template #header>
              <Checkbox
                :modelValue="allPicked('next')"
                binary
                @update:modelValue="toggleAll('next')"
              />
              <span class="ml-2">Mới</span>
            </template>
            <template #body="slotProps">
              <div class="flex align-items-center items-center justify-center">
                <Checkbox
                  :modelValue="picked.next.has(slotProps.data.id)"
                  binary
                  @update:modelValue="toggle(slotProps.data.id, 'next')"
                />
              </div>
            </template>
          </Column>
          <Column style="min-width: 5rem" frozen alignFrozen="right">
            <template #header>
              <Checkbox
                :modelValue="allPicked('today')"
                binary
                @update:modelValue="toggleAll('today')"
              />
              <span class="ml-2">Cũ</span>
            </template>
            <template #body="slotProps">
              <div class="flex align-items-center items-center justify-center">
                <Checkbox
                  :modelValue="picked.today.has(slotProps.data.id)"
                  binary
                  @update:modelValue="toggle(slotProps.data.id, 'today')"
                />
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
            class="flex-1"
          />
          <Button
            label="Tạo report"
            icon="pi pi-file"
            @click="makeReport"
            class="flex-1"
          />
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
              </div>
            </TabPanel>
            <TabPanel header="Lark">
              <div class="pre-wrap">
                <div class="pre-actions">
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
              </div>
            </TabPanel>
            <TabPanel header="Full">
              <div class="pre-wrap">
                <div class="pre-actions">
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
              </div>
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
      @show="reflowInkBar"
    >
      <div class="relative">
        <TabView ref="resultTabView" v-model:activeIndex="resultTab">
          <TabPanel header="Full">
            <div class="report-pre-wrap">
              <textarea
                v-model="resultText"
                class="report-pre"
                spellcheck="false"
              ></textarea>
            </div>
          </TabPanel>
          <TabPanel header="Chat">
            <div class="report-pre-wrap">
              <textarea
                v-model="resultText"
                class="report-pre"
                spellcheck="false"
              ></textarea>
            </div>
          </TabPanel>
          <TabPanel header="Lark">
            <div class="report-pre-wrap">
              <textarea
                v-model="resultText"
                class="report-pre"
                spellcheck="false"
              ></textarea>
            </div>
          </TabPanel>
        </TabView>
        <!-- nút nằm cùng hàng tab, dạt phải — giống reset-all ở preview ngoài -->
        <div class="dialog-tab-actions">
          <Button
            label="Copy"
            icon="pi pi-copy"
            class="p-button-outlined p-button-sm"
            @click="copyText(resultText)"
          />
          <Button
            :label="`Tải file (${reportFileName()})`"
            icon="pi pi-download"
            class="p-button-sm"
            @click="downloadReport"
          />
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
.p-multiselect-panel.report-filter-panel {
  width: max-content;
  max-width: min(22rem, 90vw);
}

.p-multiselect-panel.report-filter-panel .filter-option {
  display: block;
  min-width: 0; /* flex item mặc định min-width:auto không co được */
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
</style>
