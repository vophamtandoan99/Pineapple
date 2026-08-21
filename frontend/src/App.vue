<script setup>
import { onMounted } from 'vue';
import { usePrimeVue } from 'primevue/config';
import { loadUiSettings, useLayout } from '@/layout/composables/layout';
import { useApiLoader } from '@/service/ApiLoader';
import AppLoader from '@/components/AppLoader.vue';

const $primevue = usePrimeVue();
const { layoutConfig } = useLayout();
const { loaderActive } = useApiLoader();

onMounted(async () => {
    // Áp prefs đã lưu (theme/scale/menu...) rồi sync 2 field PrimeVue config
    // không đọc trực tiếp từ layoutConfig
    await loadUiSettings();
    $primevue.config.inputStyle = layoutConfig.inputStyle.value;
    $primevue.config.ripple = layoutConfig.ripple.value;
});
</script>

<template>
    <!-- Loader khi có API đang chạy (tối thiểu 1.5s mỗi đợt):
         overlay fixed giữa màn, phủ nhẹ + chặn click lúc chờ -->
    <Transition name="loader-fade">
        <div v-if="loaderActive" class="app-loader-overlay">
            <AppLoader />
        </div>
    </Transition>
    <!-- Toast ở gốc app: luôn mounted, sống qua mọi route change -->
    <Toast />
    <router-view />
</template>

<style scoped>
/* Overlay toàn màn: logo pulse giữa, nền mờ nhẹ theo dark/light theme,
   chặn thao tác trong lúc API chạy (tránh double-submit).
   z-index trên mask dialog PrimeVue (999/1000). */
.app-loader-overlay {
    position: fixed;
    inset: 0;
    z-index: 1100;
    display: flex;
    align-items: center;
    justify-content: center;
    background: transparent;
    /* dùng backdrop mờ để không phụ thuộc màu theme */
    backdrop-filter: blur(2px);
    background-color: rgba(0, 0, 0, 0.15);
}

/* giữa màn: logo to hơn lúc nằm trong table */
.app-loader-overlay :deep(.app-loader__logo) {
    width: 4rem;
}

/* Fade mượt khi loader bật/tắt thay vì gỡ đột ngột */
.loader-fade-enter-active,
.loader-fade-leave-active {
    transition: opacity 0.3s ease;
}

.loader-fade-enter-from,
.loader-fade-leave-to {
    opacity: 0;
}
</style>
