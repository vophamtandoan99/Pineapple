<script setup>
// Editor list rule {"type", "state", "by", "pick"} cho Cài đặt: chọn type +
// state rồi thêm vào list box, xóa từng dòng được. 2 checkbox mỗi dòng:
// "Tôi" (chỉ tính khi chính tôi chuyển, bỏ check = bất kỳ ai) và "Lần cuối"
// (lấy ngày lần cuối vào state, bỏ check = lần đầu). Dùng cho cả "trạng
// thái bắt đầu" và "trạng thái kết thúc" của bảng Lark.
import { ref, computed, watch } from "vue";

const props = defineProps({
  // list rule hiện tại: [{type, state, by}]
  modelValue: { type: Array, default: () => [] },
  // danh sách work item type của project (tải sẵn ở dialog)
  witypes: { type: Array, default: () => [] },
  // mô tả rule — hiển thị giữa form chọn và list box
  hint: { type: String, default: "" },
});
const emit = defineEmits(["update:modelValue"]);

// form thêm rule: type đang chọn + state ứng với type đó
const ruleType = ref("");
const ruleState = ref("");
const wistates = ref([]);

// đổi loại -> tải states của loại đó, xóa state đã chọn (không thuộc loại mới)
const loadStates = async (t) => {
  if (!t) {
    wistates.value = [];
    return;
  }
  try {
    const r = await fetch(`/api/workitemstates?type=${encodeURIComponent(t)}`);
    const j = await r.json().catch(() => ({}));
    wistates.value = r.ok ? j.states || [] : [];
  } catch {
    wistates.value = [];
  }
};
watch(ruleType, (t) => {
  ruleState.value = "";
  loadStates(t);
});

// loại đã có trong list -> bấm nút sẽ update state của dòng đó (không thêm dòng mới)
const isUpdate = computed(() =>
  props.modelValue.some((r) => r.type === ruleType.value),
);
const canAdd = computed(
  () =>
    !!ruleType.value &&
    !!ruleState.value &&
    !props.modelValue.some(
      (r) => r.type === ruleType.value && r.state === ruleState.value,
    ),
);
const add = () => {
  if (!canAdd.value) return;
  if (isUpdate.value) {
    // loại đã có -> đổi state, giữ nguyên "by" và "pick" người dùng đã chọn
    const i = props.modelValue.findIndex((r) => r.type === ruleType.value);
    const next = [...props.modelValue];
    next[i] = { ...next[i], type: ruleType.value, state: ruleState.value };
    emit("update:modelValue", next);
  } else {
    emit("update:modelValue", [
      ...props.modelValue,
      { type: ruleType.value, state: ruleState.value, by: ["me", "other"], pick: "first" },
    ]);
  }
  ruleState.value = ""; // giữ nguyên type để chọn state khác
};
const remove = (i) => {
  const next = [...props.modelValue];
  next.splice(i, 1);
  emit("update:modelValue", next);
};
// "by" của rule qua 1 checkbox: check = chỉ tôi chuyển ("me"), không check =
// bất kỳ ai ("me" + "other"). Rule cũ không có by = không check (any).
const meOn = (r) => r.by && r.by.length === 1 && r.by[0] === "me";
const toggleMe = (i, on) => {
  const next = [...props.modelValue];
  next[i] = { ...next[i], by: on ? ["me"] : ["me", "other"] };
  emit("update:modelValue", next);
};
// "pick": check = lần cuối vào state, bỏ check = lần đầu. Item active
// nhiều lần (active → resolved → reactivated) sẽ lấy ngày khác nhau.
const pickLast = (r) => r.pick === "last";
const togglePick = (i, on) => {
  const next = [...props.modelValue];
  next[i] = { ...next[i], pick: on ? "last" : "first" };
  emit("update:modelValue", next);
};
const label = (r) => (r.type ? `${r.type} — ${r.state}` : `Mọi loại — ${r.state}`);
</script>

<template>
  <div class="flex flex-column gap-2">
    <!-- form: chọn type + state rồi thêm vào list -->
    <div class="flex align-items-end gap-2 flex-wrap">
      <div class="flex flex-column gap-2 flex-1 min-w-10rem">
        <label class="text-500 text-sm">Loại work item</label>
        <Dropdown
          v-model="ruleType"
          :options="witypes"
          placeholder="Chọn loại"
          :disabled="!witypes.length"
          class="w-full" />
      </div>
      <div class="flex flex-column gap-2 flex-1 min-w-10rem">
        <label class="text-500 text-sm">Trạng thái</label>
        <Dropdown
          v-model="ruleState"
          :options="wistates"
          placeholder="Chọn trạng thái"
          :disabled="!ruleType"
          class="w-full" />
      </div>
      <Button
        :icon="isUpdate ? 'pi pi-pencil' : 'pi pi-plus'"
        :disabled="!canAdd"
        v-tooltip.bottom="
          isUpdate ? 'Cập nhật trạng thái của loại' : 'Thêm vào danh sách'
        "
        @click="add()" />
    </div>
    <small v-if="!witypes.length" class="text-500 text-xs"
      >Không tải được danh sách loại (chưa chọn dự án hoặc lỗi TFS)</small
    >
    <small v-else-if="hint" class="text-500 text-xs">{{ hint }}</small>
    <!-- list box các rule đã thêm -->
    <div v-if="modelValue.length" class="rule-list">
      <div
        v-for="(r, i) in modelValue"
        :key="`${r.type}|${r.state}`"
        class="rule-item flex-wrap"
      >
        <i class="pi pi-tag text-500 text-sm"></i>
        <span class="flex-1 min-w-0">{{ label(r) }}</span>
        <span
          class="flex align-items-center justify-content-center gap-2 mr-3"
          v-tooltip.bottom="'Check: chỉ tính khi chính tôi chuyển sang trạng thái này. Bỏ check: bất kỳ ai'"
        >
          <Checkbox
            :modelValue="meOn(r)"
            :binary="true"
            @update:modelValue="(v) => toggleMe(i, v)" />
          <small class="text-500 text-xs">Tôi chuyển</small>
        </span>
        <span
          class="flex align-items-center justify-content-center gap-2"
          v-tooltip.bottom="'Check: lần CUỐI vào trạng thái (item active nhiều lần). Bỏ check: lần đầu'"
        >
          <Checkbox
            :modelValue="pickLast(r)"
            :binary="true"
            @update:modelValue="(v) => togglePick(i, v)" />
          <small class="text-500 text-xs">Sau cùng</small>
        </span>
        <span class="flex-1"></span>
        <button type="button" class="p-link rule-remove" @click="remove(i)">
          <i class="pi pi-times text-sm"></i>
        </button>
      </div>
    </div>
    <small v-else class="text-500 text-xs"
      >Chưa có mục nào — chọn loại + trạng thái rồi bấm “+”.</small
    >
  </div>
</template>

<style lang="scss" scoped>
/* list box rule */
.rule-list {
  border: 1px solid var(--surface-border);
  border-radius: 6px;
  max-height: 12rem;
  overflow-y: auto;
}
.rule-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid var(--surface-border);
}
.rule-item:last-child {
  border-bottom: none;
}
.rule-remove {
  color: var(--text-color-secondary);
  border: none;
  background: transparent;
  cursor: pointer;
  padding: 0.25rem;
  border-radius: 4px;
}
.rule-remove:hover {
  background: var(--surface-hover);
  color: var(--red-500);
}
</style>
