<script setup>
import { useLayout } from "@/layout/composables/layout";
import { computed } from "vue";

const { layoutConfig } = useLayout();

const logoUrl = computed(() => {
  return `/layout/images/${
    layoutConfig.darkTheme.value ? "logo-light" : "logo-dark"
  }.svg`;
});

const year = new Date().getFullYear();
</script>

<template>
  <div class="layout-footer">
    <img :src="logoUrl" alt="Logo" height="30" class="mr-2 -mt-1.5 rotate-12" />
    <span class="ml-2 italic text-sm">
      Copyright {{ year }} Copyright by Doan Vo. All Rights Reserved
    </span>
  </div>
</template>
<style lang="scss" scoped></style>
