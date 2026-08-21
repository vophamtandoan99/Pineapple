<script setup>
// MultiSelect có nút ✕ clear khi đã chọn — PrimeVue v3 MultiSelect không có
// showClear (v4 mới thêm). Wrapper: mọi prop/slot/event truyền thẳng qua
// $attrs + $slots xuống MultiSelect bên trong, riêng class giữ lại trên div
// root: div này mới là flex item của hàng filter (class="flex-1 min-w-0"
// đặt ở component phải ăn vào đây, không phải span.p-multiselect bên trong).
import { computed, useAttrs } from "vue";
import MultiSelect from "primevue/multiselect";

defineOptions({ inheritAttrs: false });
const model = defineModel({ type: Array, default: () => [] });
const attrs = useAttrs();
const msAttrs = computed(() => {
  const { class: _class, ...rest } = attrs;
  return rest;
});
</script>

<template>
  <div class="relative w-full" :class="attrs.class">
    <MultiSelect v-model="model" v-bind="msAttrs" class="w-full">
      <template v-for="(_, name) in $slots" #[name]="slotProps" :key="name">
        <slot :name="name" v-bind="slotProps" />
      </template>
    </MultiSelect>
    <i
      v-if="model && model.length"
      class="pi pi-times multiselect-clear-icon"
      @click="model = []"></i>
  </div>
</template>

<style scoped>
/* nút ✕: nằm trước dropdown icon của MultiSelect (~2.5rem bên phải input) */
.multiselect-clear-icon {
  position: absolute;
  top: 50%;
  right: 2.75rem;
  margin-top: -0.5rem;
  cursor: pointer;
  font-size: 0.875rem;
  color: var(--text-color-secondary);
  z-index: 1;
}

.multiselect-clear-icon:hover {
  color: var(--text-color);
}
</style>
