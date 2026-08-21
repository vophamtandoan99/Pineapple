<script setup>
import { useLayout } from "@/layout/composables/layout";
import { computed } from "vue";

const { layoutConfig } = useLayout();

const logoUrl = computed(() => {
  return `/layout/images/${
    layoutConfig.darkTheme.value ? "logo-white" : "logo-dark"
  }.svg`;
});
</script>

<template>
  <div class="layout-footer">
    <img :src="logoUrl" alt="Logo" height="30" class="mr-2 -mt-1.5 rotate-12" />
    by
    <span class="font-medium ml-2">Đoan Võ</span>
  </div>
</template>
<style lang="scss" scoped></style>
