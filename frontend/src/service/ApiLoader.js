import { ref } from 'vue';

// Loader toàn app: hiện khi có API đang chạy, mỗi đợt tối thiểu MIN_MS
// (kể cả khi API trả về nhanh) — tránh loader nhấp nháy.
// Nhiều call chồng chéo: loader tắt khi call cuối xong + đủ thời gian tối thiểu.
const loaderActive = ref(false);
const MIN_MS = 1500;

let activeCount = 0;
let shownAt = 0;
let hideTimer = null;

const maybeHide = () => {
    if (activeCount > 0) return;
    clearTimeout(hideTimer);
    const remaining = Math.max(0, MIN_MS - (Date.now() - shownAt));
    hideTimer = setTimeout(() => {
        // Call mới có thể vào trong lúc chờ — chỉ tắt khi thật sự rảnh
        if (activeCount === 0) loaderActive.value = false;
    }, remaining);
};

// fetch() drop-in: cùng chữ ký, thêm hiển thị loader.
// opts.silent = true: không hiện loader toàn app (dùng khi UI đã có loading riêng)
export async function apiFetch(url, { silent = false, ...opts } = {}) {
    if (silent) return fetch(url, opts);

    activeCount++;
    if (!loaderActive.value) {
        clearTimeout(hideTimer);
        loaderActive.value = true;
        shownAt = Date.now();
    }
    try {
        return await fetch(url, opts);
    } finally {
        activeCount--;
        maybeHide();
    }
}

export function useApiLoader() {
    return { loaderActive };
}
