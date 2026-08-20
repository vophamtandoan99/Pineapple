<script setup>
// Vùng list dùng chung cho 2 StepperPanel (collection / project)
defineProps({
    loading: Boolean,
    error: String,
    rows: { type: Array, default: () => [] },
    emptyText: String,
    isProject: Boolean,
    picking: String,
    styleAt: { type: Function, required: true },
    rowSubtitle: { type: Function, required: true }
});

defineEmits(['pick', 'retry']);
</script>

<template>
    <div class="w-full flex flex-column">
        <!-- loading -->
        <template v-if="loading">
            <div v-for="i in 3" :key="i" class="w-full flex align-items-center py-5 border-300 border-bottom-1">
                <Skeleton width="3.5rem" height="3.5rem" border-radius="6px" class="flex-shrink-0" />
                <div class="ml-4 flex flex-column w-full">
                    <Skeleton width="60%" height="1.5rem" class="mb-2" />
                    <Skeleton width="40%" height="1rem" />
                </div>
            </div>
        </template>

        <!-- error -->
        <div v-else-if="error" class="w-full flex flex-column align-items-center py-6">
            <i class="pi pi-exclamation-triangle text-yellow-500 text-4xl mb-3"></i>
            <div class="text-muted mb-4 text-center">{{ error }}</div>
            <Button label="Thử lại" icon="pi pi-refresh" @click="$emit('retry')" />
        </div>

        <!-- empty -->
        <div v-else-if="!rows.length" class="w-full flex flex-column align-items-center py-6">
            <i class="pi pi-folder-open text-muted text-4xl mb-3"></i>
            <div class="text-muted">{{ emptyText }}</div>
        </div>

        <!-- list: clone row style NotFound -->
        <template v-else>
            <button
                v-for="(item, i) in rows"
                :key="item.id || item.name"
                type="button"
                class="picker-row px-2 w-full flex align-items-center py-5 border-bottom-1 cursor-pointer bg-transparent border-none p-0 text-left transition-colors transition-duration-200"
                :class="{ 'opacity-50 pointer-events-none': picking && picking !== item.name }"
                @click="$emit('pick', item)"
            >
                <span class="flex justify-content-center align-items-center border-round flex-shrink-0" :class="styleAt(i).bg" style="height: 3.5rem; width: 3.5rem">
                    <i v-if="isProject && picking === item.name" class="text-50 pi pi-fw pi-spinner pi-spin text-2xl"></i>
                    <i v-else class="text-50 pi pi-fw text-2xl" :class="styleAt(i).icon"></i>
                </span>
                <span class="ml-4 flex flex-column min-w-0">
                    <span class="picker-name lg:text-xl font-medium mb-0 block white-space-nowrap overflow-hidden text-overflow-ellipsis">{{ item.name }}</span>
                    <span class="text-muted lg:text-xl white-space-nowrap overflow-hidden text-overflow-ellipsis">{{ rowSubtitle(item) }}</span>
                </span>
                <i v-if="!isProject" class="pi pi-chevron-right text-muted ml-auto"></i>
            </button>
        </template>
    </div>
</template>

<style scoped>
/* Màu theo theme (var của PrimeVue theme) — đúng cả dark mode */
.text-muted {
    color: var(--text-color-secondary);
}
.picker-name {
    color: var(--text-color);
}
.picker-row {
    border-color: var(--surface-border);
}
.picker-row:hover {
    background: var(--surface-hover);
}
</style>
