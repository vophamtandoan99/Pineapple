<script setup>
// Logo Pineapple pulse — loader thương hiệu dùng chung (login, chọn
// collection/project, loading table...). CSS global (không scoped) để
// mọi nơi import đều dùng chung 1 định nghĩa.
import { computed } from "vue";
import { useLayout } from "@/layout/composables/layout";

const { layoutConfig } = useLayout();
const logoUrl = computed(
  () =>
    `/layout/images/${
      layoutConfig.darkTheme.value ? "logo-light" : "logo-dark"
    }.svg`,
);
</script>

<template>
  <div class="app-loader__wrap">
    <img :src="logoUrl" alt="Đang tải" class="app-loader__logo" />
  </div>
</template>

<style>
.app-loader__wrap {
  display: flex;
  align-items: center;
  justify-content: center;
}

.app-loader__logo {
  width: 3rem;
  transform: rotate(12deg);
  animation: app-loader-pulse 1.2s ease-in-out infinite;
}

@keyframes app-loader-pulse {
  0%,
  100% {
    transform: scale(1) rotate(12deg);
    opacity: 1;
  }
  50% {
    transform: scale(0.85) rotate(12deg);
    opacity: 0.6;
  }
}
</style>
