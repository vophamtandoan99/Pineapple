<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue';
import { useLayout } from '@/layout/composables/layout';
import { useRouter } from 'vue-router';
import { useConfirm } from 'primevue/useconfirm';
import { useAuth } from '@/service/AuthService';
import { useProject } from '@/service/ProjectService';

const { layoutConfig, onMenuToggle } = useLayout();

const outsideClickListener = ref(null);
const topbarMenuActive = ref(false);
const isMobile = ref(window.innerWidth < 991);
const onResize = () => {
    isMobile.value = window.innerWidth < 991;
};
const router = useRouter();
const confirm = useConfirm();
const { user, fullname, clearUser } = useAuth();
const { currentCollection, currentProject } = useProject();
const userDialog = ref(false);

// chữ cái đầu làm avatar
const initials = computed(() => {
    const name = fullname.value || user.value || '?';
    return name
        .split(/\s+/)
        .map((w) => w[0])
        .slice(-2)
        .join('')
        .toUpperCase();
});

// ---------- notifications ----------
const op = ref(null);
const notifItems = ref([]);
const typeColors = { Epic: '#f97316', 'User Story': '#3b82f6', Task: '#eab308', Bug: '#ef4444' };
const toggleNotifs = (event) => op.value.toggle(event);
const fmtDate = (iso) => {
    if (!iso) return '';
    const [y, m, d] = iso.slice(0, 10).split('-');
    return y ? `${d}/${m}` : iso;
};

onMounted(() => {
    bindOutsideClickListener();
    window.addEventListener('resize', onResize);
});

onBeforeUnmount(() => {
    unbindOutsideClickListener();
    window.removeEventListener('resize', onResize);
});

const logoUrl = computed(() => {
    return `/layout/images/${layoutConfig.darkTheme.value ? 'logo-white' : 'logo-dark'}.svg`;
});

const onTopBarMenuButton = () => {
    topbarMenuActive.value = !topbarMenuActive.value;
};
const performLogout = async () => {
    topbarMenuActive.value = false;
    try {
        await fetch('/api/logout', { method: 'POST' });
    } catch (e) {
        // bỏ qua lỗi mạng — vẫn reset state phía client
    }
    clearUser();
    await router.push('/auth/login');
};
const onLogoutClick = () => {
    topbarMenuActive.value = false;
    confirm.require({
        message: 'Bạn có chắc chắn muốn đăng xuất?',
        header: 'Xác nhận đăng xuất',
        icon: 'pi pi-sign-out text-red-500',
        acceptLabel: 'Đăng xuất',
        rejectLabel: 'Hủy',
        acceptClass: 'p-button-danger',
        accept: performLogout
    });
};
const topbarMenuClasses = computed(() => {
    return {
        'layout-topbar-menu-mobile-active': topbarMenuActive.value
    };
});

const bindOutsideClickListener = () => {
    if (!outsideClickListener.value) {
        outsideClickListener.value = (event) => {
            if (isOutsideClicked(event)) {
                topbarMenuActive.value = false;
            }
        };
        document.addEventListener('click', outsideClickListener.value);
    }
};
const unbindOutsideClickListener = () => {
    if (outsideClickListener.value) {
        document.removeEventListener('click', outsideClickListener);
        outsideClickListener.value = null;
    }
};
const isOutsideClicked = (event) => {
    if (!topbarMenuActive.value) return;

    const sidebarEl = document.querySelector('.layout-topbar-menu');
    const topbarEl = document.querySelector('.layout-topbar-menu-button');

    return !(sidebarEl.isSameNode(event.target) || sidebarEl.contains(event.target) || topbarEl.isSameNode(event.target) || topbarEl.contains(event.target));
};
</script>

<template>
    <div class="layout-topbar">
       

        <button class="p-link layout-menu-button layout-topbar-button" v-tooltip.bottom="!isMobile ? 'Thu gọn / mở menu' : undefined" @click="onMenuToggle()">
            <i class="pi pi-bars"></i>
        </button>

        <button class="p-link layout-topbar-menu-button layout-topbar-button" @click="onTopBarMenuButton()">
            <i class="pi pi-ellipsis-v"></i>
        </button>

         <router-link to="/" class="layout-topbar-logo">
            <img :src="logoUrl" alt="logo" class="size-6" />
            <span>Pineapple</span>
        </router-link>

        <button class="p-link layout-topbar-fullname" v-tooltip.bottom="'Xem thông tin'" @click="userDialog = true">
            <span>{{ fullname || user }}</span>
        </button>

        <div class="layout-topbar-menu" :class="topbarMenuClasses">
            <router-link to="/projects" class="p-link layout-topbar-button" v-tooltip.bottom="!isMobile ? 'Đổi dự án' : undefined">
                <i class="pi pi-th-large"></i>
                <span>Đổi dự án</span>
            </router-link>
            <button @click="userDialog = true" class="p-link layout-topbar-button" v-tooltip.bottom="!isMobile ? (fullname || user) : undefined">
                <i class="pi pi-user"></i>
                <span>{{ fullname || user }}</span>
            </button>
            <button @click="onLogoutClick()" class="p-link layout-topbar-button" v-tooltip.bottom="!isMobile ? 'Đăng xuất' : undefined">
                <i class="pi pi-sign-out text-red-500"></i>
                <span>Đăng xuất</span>
            </button>
        </div>

        <!-- user info modal -->
        <Dialog v-model:visible="userDialog" modal :dismissableMask="true" :focusOnShow="false" :style="{ width: '32rem' }" header="Thông tin tài khoản" class="user-dialog">
            <div class="flex align-items-center gap-3 py-2">
                <div class="flex align-items-center justify-content-center border-circle user-avatar flex-shrink-0">{{ initials }}</div>
                <div class="min-w-0">
                    <div class="text-900 text-xl font-medium">{{ fullname || '—' }}</div>
                    <div class="text-500 mt-1 flex align-items-center gap-2">
                        <i class="pi pi-user text-sm"></i>
                        {{ user || '—' }}
                    </div>
                    <div v-if="currentProject" class="text-500 mt-1 flex align-items-center gap-2">
                        <i class="pi pi-th-large text-sm"></i>
                        {{ currentCollection ? `${currentCollection}/` : '' }}{{ currentProject }}
                    </div>
                </div>
            </div>
        </Dialog>
    </div>
</template>

<style lang="scss" scoped>
.layout-topbar-fullname {
    margin-left: auto;
    margin-right: 1rem;
    color: var(--text-color-secondary);
    font-weight: 600;
    font-size: 0.95rem;
    white-space: nowrap;
    display: flex;
    align-items: center;
    background: transparent;
    border: none;
    cursor: pointer;
    padding: 0.4rem 0.75rem;
    border-radius: 6px;

    &:hover {
        background: var(--surface-hover);
        color: var(--text-color);
    }
}

.layout-topbar-menu {
    margin-left: 0 !important;
}

@media (max-width: 991px) {
    .layout-topbar-fullname {
        display: none;
    }
}

.user-avatar {
    width: 5.5rem;
    height: 5.5rem;
    background: var(--primary-color);
    color: var(--primary-color-text);
    font-size: 1.75rem;
    font-weight: 600;
}

/* nút close dialog: bỏ viền/nền */
:deep(.p-dialog-header .p-dialog-header-icon) {
    border: none;
    background: transparent;
    box-shadow: none;
}
</style>

<style lang="scss">
/* Dialog teleport ra body nên cần style global */
.user-dialog .p-dialog-header .p-dialog-header-icon {
    border: none;
    background: transparent;
    box-shadow: none;
}
</style>
