import { toRefs, reactive, computed, watch } from 'vue';

const layoutConfig = reactive({
    ripple: true,
    darkTheme: false,
    inputStyle: 'outlined',
    menuMode: 'static',
    theme: 'aura-light-blue',
    scale: 14,
    activeMenuItem: null
});

const layoutState = reactive({
    staticMenuDesktopInactive: false,
    overlayMenuActive: false,
    profileSidebarVisible: false,
    configSidebarVisible: false,
    staticMenuMobileActive: false,
    menuHoverActive: false
});

// ---------- persist UI prefs vào config backend ----------
const UI_KEYS = ['ripple', 'darkTheme', 'inputStyle', 'menuMode', 'theme', 'scale'];
let saveTimer = null;
let uiWatchersStarted = false;

// Debounce 500ms: kéo scale liên tục chỉ ghi 1 lần
const saveUiSettings = () => {
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = setTimeout(() => {
        const patch = {};
        for (const k of UI_KEYS) patch[k] = layoutConfig[k];
        fetch('/api/ui-settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(patch)
        }).catch(() => {
            // fail im lặng — prefs không được quan trọng bằng chức năng chính
        });
    }, 500);
};

const startUiWatchers = () => {
    if (uiWatchersStarted) return;
    uiWatchersStarted = true;
    for (const k of UI_KEYS) {
        watch(() => layoutConfig[k], saveUiSettings);
    }
};

const applyThemeCss = (theme) => {
    const link = document.getElementById('theme-css');
    if (link) link.href = `/themes/${theme}/theme.css`;
};

// Load prefs từ backend, áp dụng, SAU ĐÓ mới bật watcher để không tự lưu
// ngược giá trị vừa load. Trả về prefs đã áp dụng để caller sync PrimeVue.
export async function loadUiSettings() {
    try {
        const r = await fetch('/api/ui-settings');
        if (!r.ok) return layoutConfig;
        const ui = await r.json();
        for (const k of UI_KEYS) {
            if (ui[k] !== undefined && ui[k] !== null) layoutConfig[k] = ui[k];
        }
        applyThemeCss(layoutConfig.theme);
        document.documentElement.style.fontSize = layoutConfig.scale + 'px';
    } catch (e) {
        // offline / chưa đăng nhập -> giữ default
    }
    startUiWatchers();
    return layoutConfig;
}

export function useLayout() {
    const setScale = (scale) => {
        layoutConfig.scale = scale;
    };

    const setActiveMenuItem = (item) => {
        layoutConfig.activeMenuItem = item.value || item;
    };

    const onMenuToggle = () => {
        if (layoutConfig.menuMode === 'overlay') {
            layoutState.overlayMenuActive = !layoutState.overlayMenuActive;
        }

        if (window.innerWidth > 991) {
            layoutState.staticMenuDesktopInactive = !layoutState.staticMenuDesktopInactive;
        } else {
            layoutState.staticMenuMobileActive = !layoutState.staticMenuMobileActive;
        }
    };

    const isSidebarActive = computed(() => layoutState.overlayMenuActive || layoutState.staticMenuMobileActive);

    const isDarkTheme = computed(() => layoutConfig.darkTheme);

    return { layoutConfig: toRefs(layoutConfig), layoutState: toRefs(layoutState), setScale, onMenuToggle, isSidebarActive, isDarkTheme, setActiveMenuItem };
}
