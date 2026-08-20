import { ref } from 'vue';
import { useProject } from './ProjectService';

// Trạng thái đăng nhập dùng chung toàn app (module scope)
const user = ref(null);
const fullname = ref('');
let sessionPromise = null;

const { setCurrentProject, clearProject } = useProject();

// Kiểm tra session backend qua cookie.
// Chỉ cache kết quả THÀNH CÔNG — thất bại phải check lại lần sau
// (vì user có thể login xong ngay sau đó, cache false sẽ chặn navigation).
function checkSession(force = false) {
    if (force) sessionPromise = null;
    if (!sessionPromise) {
        const p = fetch('/api/me')
            .then(async (r) => {
                if (!r.ok) {
                    user.value = null;
                    fullname.value = '';
                    sessionPromise = null; // không cache thất bại
                    return false;
                }
                const j = await r.json();
                user.value = j.user;
                fullname.value = j.fullname || '';
                setCurrentProject(j.collection, j.project);
                return true;
            })
            .catch(() => {
                user.value = null;
                fullname.value = '';
                sessionPromise = null; // lỗi mạng: thử lại lần sau
                return false;
            });
        if (!sessionPromise) sessionPromise = p;
    }
    return sessionPromise;
}

// Gọi sau khi login thành công
function setUser(data) {
    user.value = data.user;
    fullname.value = data.fullname || '';
    setCurrentProject('', '');
    sessionPromise = Promise.resolve(true);
}

// Gọi sau khi logout
function clearUser() {
    user.value = null;
    fullname.value = '';
    clearProject();
    sessionPromise = null;
}

// Token/session hết hạn (API trả 401): logout backend, clear state, toast, về login
function sessionExpired(toast, router) {
    fetch('/api/logout', { method: 'POST' }).catch(() => {});
    clearUser();
    toast?.add({ severity: 'warn', summary: 'Phiên đăng nhập hết hạn', detail: 'Vui lòng đăng nhập lại', life: 4000 });
    router.push('/auth/login');
}

export function useAuth() {
    return { user, fullname, checkSession, setUser, clearUser, sessionExpired };
}
