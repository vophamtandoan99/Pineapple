import { ref } from 'vue';
import { apiFetch } from './ApiLoader';

// Trạng thái collection/project dùng chung toàn app (module scope).
// Lựa chọn được lưu phía server trong session — reload trang vẫn giữ.
const collections = ref([]);
const projects = ref([]);
const currentCollection = ref('');
const currentProject = ref('');
let collectionsPromise = null;
let projectsPromise = null;
let loadedCollection = '';

// Lấy danh sách collection (cấp 1).
// Cache kết quả THÀNH CÔNG — thất bại phải check lại lần sau.
function loadCollections(force = false) {
    if (force) collectionsPromise = null;
    if (!collectionsPromise) {
        const p = apiFetch('/api/collections', { silent: true })
            .then(async (r) => {
                const j = await r.json().catch(() => ({}));
                if (!r.ok) {
                    collectionsPromise = null;
                    return { ok: false, error: j.error || `Lỗi HTTP ${r.status}` };
                }
                collections.value = j.collections || [];
                return { ok: true, error: '' };
            })
            .catch((e) => {
                collectionsPromise = null;
                return { ok: false, error: e.message || 'Lỗi mạng' };
            });
        if (!collectionsPromise) collectionsPromise = p;
    }
    return collectionsPromise;
}

// Lấy danh sách project trong một collection (cấp 2).
// Cache theo collection vừa load — đổi collection thì fetch lại.
function loadProjects(collection, force = false) {
    if (force || loadedCollection !== collection) {
        projectsPromise = null;
    }
    if (!projectsPromise) {
        const p = apiFetch(`/api/projects?collection=${encodeURIComponent(collection)}`, { silent: true })
            .then(async (r) => {
                const j = await r.json().catch(() => ({}));
                if (!r.ok) {
                    projectsPromise = null;
                    return { ok: false, error: j.error || `Lỗi HTTP ${r.status}` };
                }
                projects.value = j.projects || [];
                loadedCollection = collection;
                return { ok: true, error: '' };
            })
            .catch((e) => {
                projectsPromise = null;
                return { ok: false, error: e.message || 'Lỗi mạng' };
            });
        if (!projectsPromise) projectsPromise = p;
    }
    return projectsPromise;
}

// Chọn collection + project — server ghi vào session
async function selectProject(collection, name) {
    const r = await apiFetch('/api/select-project', {
        silent: true,
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ collection, project: name })
    });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.error || 'Lỗi chọn dự án');
    currentCollection.value = collection;
    currentProject.value = name;
    return true;
}

// Đồng bộ từ response /api/me
function setCurrentProject(collection, project) {
    currentCollection.value = collection || '';
    currentProject.value = project || '';
}

// Gọi sau khi logout
function clearProject() {
    collections.value = [];
    projects.value = [];
    currentCollection.value = '';
    currentProject.value = '';
    collectionsPromise = null;
    projectsPromise = null;
    loadedCollection = '';
}

export function useProject() {
    return { collections, projects, currentCollection, currentProject, loadCollections, loadProjects, selectProject, setCurrentProject, clearProject };
}
