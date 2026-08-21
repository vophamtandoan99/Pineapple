<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from "vue";
import { useLayout } from "@/layout/composables/layout";
import { useRouter } from "vue-router";
import { useConfirm } from "primevue/useconfirm";
import { useToast } from "primevue/usetoast";
import { useAuth } from "@/service/AuthService";
import { useProject } from "@/service/ProjectService";
import RuleEditor from "@/components/RuleEditor.vue";

const { layoutConfig, onMenuToggle } = useLayout();
const toast = useToast();

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

// ---------- settings ----------
const settingsDialog = ref(false);
const settingsLoading = ref(false);
const settingsSaving = ref(false);
// trạng thái mặc định từ default.json (backend kèm theo GET /api/settings)
const settingsDefaults = ref(null);
const settings = ref({ server: "", org: "", fullname: "", larkRules: [], larkEndRules: [], percentMode: "work", fullnameFallbackUser: true, hasToken: false });
// cách tính % trong report: ưu tiên Remaining/Completed work, hoặc theo trạng thái
const percentModes = [
  { label: "Theo Remaining/Completed work", value: "work" },
  { label: "Theo trạng thái", value: "state" },
];
// danh sách work item type của project hiện tại (lấy khi mở dialog)
const witypes = ref([]);
const openSettings = async () => {
  settingsDialog.value = true;
  settingsLoading.value = true;
  try {
    const r = await fetch("/api/settings");
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.error || "Lỗi tải cấu hình");
    settings.value = j;
    settingsDefaults.value = j.defaults || null;
    // Tên hiển thị: điền sẵn theo display name thật từ TFS (session hiện tại),
    // thiếu thì giữ giá trị config cũ
    settings.value.fullname = fullname.value || j.fullname || "";
    // loại work item: lỗi (chưa chọn dự án...) thì list rỗng, không chặn dialog
    try {
      const rt = await fetch("/api/workitemtypes");
      const jt = await rt.json().catch(() => ({}));
      witypes.value = rt.ok ? jt.types || [] : [];
    } catch {
      witypes.value = [];
    }
  } catch (e) {
    toast.add({ severity: "error", summary: "Lỗi", detail: e.message, life: 4000 });
    settingsDialog.value = false;
  } finally {
    settingsLoading.value = false;
  }
};
// form rule (type + state, list box) gói trong RuleEditor — dùng cho start + end

// trạng thái bắt đầu và kết thúc của cùng 1 loại phải KHÁC nhau;
// type rỗng ("Mọi loại") coi như trùng với mọi loại. Trả nhãn loại lỗi, null = hợp lệ.
const ruleConflict = (starts, ends) => {
  for (const s of starts)
    for (const e of ends)
      if (s.state === e.state && (!s.type || !e.type || s.type === e.type))
        return `${s.type || e.type || "Mọi loại"} — ${s.state}`;
  return null;
};
// bật/tắt "ai chuyển state" trên từng rule — đặt trong RuleEditor

// Reset form về default.json — chưa ghi config, user bấm Lưu mới lưu
const resetSettings = () => {
  const d = settingsDefaults.value;
  if (!d) return;
  settings.value = {
    ...settings.value,
    server: d.server,
    org: d.org,
    // tên hiển thị ưu tiên display name TFS rồi mới tới default
    fullname: fullname.value || d.fullname || "",
    larkRules: d.larkRules || [],
    larkEndRules: d.larkEndRules || [],
    percentMode: d.percentMode || "work",
    fullnameFallbackUser: d.fullnameFallbackUser !== false,
  };
  toast.add({ severity: "info", summary: "Đã áp mặc định", detail: "Bấm Lưu để ghi vào config", life: 3000 });
};

const saveSettings = async () => {
  if (settingsSaving.value) return;
  const bad = ruleConflict(settings.value.larkRules || [], settings.value.larkEndRules || []);
  if (bad) {
    toast.add({
      severity: "error",
      summary: "Quy tắc mâu thuẫn",
      detail: `Trạng thái bắt đầu và kết thúc của "${bad}" phải khác nhau`,
      life: 5000,
    });
    return;
  }
  settingsSaving.value = true;
  try {
    const r = await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        server: settings.value.server,
        org: settings.value.org,
        fullname: settings.value.fullname,
        larkRules: settings.value.larkRules,
        larkEndRules: settings.value.larkEndRules,
        percentMode: settings.value.percentMode,
        fullnameFallbackUser: settings.value.fullnameFallbackUser,
      }),
    });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.error || "Lỗi lưu cấu hình");
    settingsDialog.value = false;
    toast.add({ severity: "success", summary: "Đã lưu cấu hình", life: 3000 });
    // báo các view (Report) nạp lại dữ liệu theo config mới: %, tên, ngày
    // start/end theo rules...
    window.dispatchEvent(new CustomEvent("settings-updated"));
  } catch (e) {
    toast.add({ severity: "error", summary: "Lỗi", detail: e.message, life: 4000 });
  } finally {
    settingsSaving.value = false;
  }
};

// chữ cái đầu làm avatar
const initials = computed(() => {
  const name = fullname.value || user.value || "?";
  return name
    .split(/\s+/)
    .map((w) => w[0])
    .slice(-2)
    .join("")
    .toUpperCase();
});

// ---------- notifications ----------
const op = ref(null);
const notifItems = ref([]);
const typeColors = {
  Epic: "#f97316",
  "User Story": "#3b82f6",
  Task: "#eab308",
  Bug: "#ef4444",
};
const toggleNotifs = (event) => op.value.toggle(event);
const fmtDate = (iso) => {
  if (!iso) return "";
  const [y, m, d] = iso.slice(0, 10).split("-");
  return y ? `${d}/${m}` : iso;
};

onMounted(() => {
  bindOutsideClickListener();
  window.addEventListener("resize", onResize);
});

onBeforeUnmount(() => {
  unbindOutsideClickListener();
  window.removeEventListener("resize", onResize);
});

const logoUrl = computed(() => {
  return `/layout/images/${
    layoutConfig.darkTheme.value ? "logo-light" : "logo-dark"
  }.svg`;
});

const onTopBarMenuButton = () => {
  topbarMenuActive.value = !topbarMenuActive.value;
};
const performLogout = async () => {
  topbarMenuActive.value = false;
  try {
    await fetch("/api/logout", { method: "POST" });
  } catch (e) {
    // bỏ qua lỗi mạng — vẫn reset state phía client
  }
  clearUser();
  await router.push("/auth/login");
};
const onLogoutClick = () => {
  topbarMenuActive.value = false;
  confirm.require({
    message: "Bạn có chắc chắn muốn đăng xuất?",
    header: "Xác nhận đăng xuất",
    icon: "pi pi-sign-out text-red-500",
    acceptLabel: "Đăng xuất",
    rejectLabel: "Hủy",
    acceptClass: "p-button-danger",
    accept: performLogout,
  });
};
const topbarMenuClasses = computed(() => {
  return {
    "layout-topbar-menu-mobile-active": topbarMenuActive.value,
  };
});

const bindOutsideClickListener = () => {
  if (!outsideClickListener.value) {
    outsideClickListener.value = (event) => {
      if (isOutsideClicked(event)) {
        topbarMenuActive.value = false;
      }
    };
    document.addEventListener("click", outsideClickListener.value);
  }
};
const unbindOutsideClickListener = () => {
  if (outsideClickListener.value) {
    document.removeEventListener("click", outsideClickListener);
    outsideClickListener.value = null;
  }
};
const isOutsideClicked = (event) => {
  if (!topbarMenuActive.value) return;

  const sidebarEl = document.querySelector(".layout-topbar-menu");
  const topbarEl = document.querySelector(".layout-topbar-menu-button");

  return !(
    sidebarEl.isSameNode(event.target) ||
    sidebarEl.contains(event.target) ||
    topbarEl.isSameNode(event.target) ||
    topbarEl.contains(event.target)
  );
};
</script>

<template>
  <div class="layout-topbar">
    <button
      class="p-link layout-menu-button layout-topbar-button"
      v-tooltip.bottom="!isMobile ? 'Thu gọn / mở menu' : undefined"
      @click="onMenuToggle()"
    >
      <i class="pi pi-bars"></i>
    </button>

    <button
      class="p-link layout-topbar-menu-button layout-topbar-button"
      @click="onTopBarMenuButton()"
    >
      <i class="pi pi-ellipsis-v"></i>
    </button>

    <router-link to="/" class="layout-topbar-logo">
      <img :src="logoUrl" alt="logo" class="size-6 rotate-12 -mt-1.5" />
      <span>Pineapple</span>
    </router-link>

    <div class="layout-topbar-menu" :class="topbarMenuClasses">
      <button
        @click="openSettings()"
        class="p-link layout-topbar-button"
        v-tooltip.bottom="!isMobile ? 'Cài đặt' : undefined"
      >
        <i class="pi pi-cog"></i>
        <span>Cài đặt</span>
      </button>
      <router-link
        to="/projects"
        class="p-link layout-topbar-button"
        v-tooltip.bottom="!isMobile ? 'Đổi dự án' : undefined"
      >
        <i class="pi pi-th-large"></i>
        <span>Đổi dự án</span>
      </router-link>
      <button
        @click="userDialog = true"
        class="p-link layout-topbar-button"
        v-tooltip.bottom="!isMobile ? 'Thông tin tài khoản' : undefined"
      >
        <i class="pi pi-user"></i>
        <span>Thông tin</span>
      </button>
      <button
        @click="onLogoutClick()"
        class="p-link layout-topbar-button"
        v-tooltip.bottom="!isMobile ? 'Đăng xuất' : undefined"
      >
        <i class="pi pi-sign-out text-red-500"></i>
        <span>Đăng xuất</span>
      </button>
    </div>

    <!-- user info modal -->
    <Dialog
      v-model:visible="userDialog"
      modal
      :dismissableMask="true"
      :focusOnShow="false"
      :style="{ width: '32rem' }"
      header="Thông tin tài khoản"
      class="user-dialog"
    >
      <div class="flex align-items-center gap-3 py-2">
        <div
          class="flex align-items-center justify-content-center border-circle user-avatar flex-shrink-0"
        >
          {{ initials }}
        </div>
        <div class="min-w-0">
          <div class="text-900 text-xl font-medium">{{ fullname || "—" }}</div>
          <div class="text-500 mt-1 flex align-items-center gap-2">
            <i class="pi pi-user text-sm"></i>
            {{ user || "—" }}
          </div>
          <div
            v-if="currentProject"
            class="text-500 mt-1 flex align-items-center gap-2"
          >
            <i class="pi pi-th-large text-sm"></i>
            {{ currentCollection ? `${currentCollection}/` : ""
            }}{{ currentProject }}
          </div>
        </div>
      </div>
    </Dialog>

    <!-- settings modal -->
    <Dialog
      v-model:visible="settingsDialog"
      modal
      :dismissableMask="true"
      :style="{ width: '70rem' }"
      :breakpoints="{ '1100px': '95vw' }"
      class="user-dialog"
    >
      <!-- header custom: nút reset icon đứng cạnh nút close của dialog -->
      <template #header>
        <span class="p-dialog-title">Cài đặt</span>
        <button
          type="button"
          class="p-link settings-reset-icon"
          v-tooltip.bottom="'Áp cấu hình mặc định'"
          :disabled="!settingsDefaults || settingsLoading"
          @click="resetSettings()"
        >
          <i class="pi pi-replay"></i>
        </button>
      </template>
      <div v-if="settingsLoading" class="flex justify-content-center py-4">
        <i class="pi pi-spin pi-spinner text-2xl"></i>
      </div>
      <!-- 2 cột: trái = kết nối TFS, phải = rules bảng Lark.
           Inline style vì .grid bị Tailwind đè PrimeFlex (grid không template
           -> 1 cột), col-6 Tailwind không có -->
      <div
        v-else
        class="py-2"
        style="
          display: grid;
          grid-template-columns: minmax(0, 1fr) minmax(0, 2fr);
          gap: 1.5rem;
        "
      >
        <div class="flex flex-column gap-4">
          <div class="flex flex-column gap-2">
            <label for="set-server" class="font-medium">Server TFS</label>
            <InputText
              id="set-server"
              v-model="settings.server"
              placeholder="https://tfs.example.com"
              disabled
              class="w-full" />
          </div>
          <div class="flex flex-column gap-2">
            <label for="set-org" class="font-medium">Collection mặc định</label>
            <InputText
              id="set-org"
              v-model="settings.org"
              placeholder="VD: TMTAICollection"
              disabled
              class="w-full" />
            <small class="text-500 text-xs"
              >Dùng khi login bằng token mà không điền collection</small
            >
          </div>
          <div class="flex flex-column gap-2">
            <label for="set-fullname" class="font-medium">Tên hiển thị</label>
            <InputText
              id="set-fullname"
              v-model="settings.fullname"
              placeholder="Tên fallback khi TFS không trả về"
              class="w-full" />
            <span
              class="flex align-items-center gap-2"
              v-tooltip.bottom="'Bỏ check: dòng Nhân sự trong report để trống khi TFS không trả về display name'"
            >
              <Checkbox
                v-model="settings.fullnameFallbackUser"
                :binary="true" />
              <small class="text-500 text-xs"
                >Dùng username khi không có tên hiển thị</small
              >
            </span>
          </div>
          <div class="flex flex-column gap-2">
            <label for="set-percent" class="font-medium">Tính % công việc</label>
            <Dropdown
              id="set-percent"
              v-model="settings.percentMode"
              :options="percentModes"
              optionLabel="label"
              optionValue="value"
              placeholder="Chọn cách tính"
              class="w-full" />
            <small class="text-500 text-xs"
              >Work: % = Completed / (Completed + Remaining), item không có số
              work thì theo trạng thái.<br />
              Trạng thái: Closed/Resolved/Done = 100%, còn lại 0%.</small
            >
          </div>
          <div
            v-if="settings.hasToken"
            class="flex align-items-center gap-2 text-500"
          >
            <i class="pi pi-key text-sm"></i>
            <small class="text-xs">Token đã lưu trong config (từ "ghi nhớ đăng nhập")</small>
          </div>
        </div>
        <div class="flex flex-column gap-6">
          <div class="flex flex-column gap-2">
            <label class="font-medium">Trạng thái bắt đầu (Lark)</label>
            <RuleEditor
              v-model="settings.larkRules"
              :witypes="witypes"
              hint="Start date trong bảng Lark = ngày item vào trạng thái khớp loại trong danh sách (đọc lịch sử TFS). Danh sách rỗng = dùng ngày báo cáo." />
          </div>
          <div class="flex flex-column gap-2">
            <label class="font-medium">Trạng thái kết thúc (Lark)</label>
            <RuleEditor
              v-model="settings.larkEndRules"
              :witypes="witypes"
              hint="End date trong bảng Lark = ngày item vào trạng thái khớp loại trong danh sách. Danh sách rỗng = để trống." />
          </div>
        </div>
      </div>
      <template #footer>
        <Button
          label="Hủy"
          severity="secondary"
          @click="settingsDialog = false"
          text />
        <Button
          label="Lưu"
          :loading="settingsSaving"
          @click="saveSettings()" />
      </template>
    </Dialog>
  </div>
</template>

<style lang="scss" scoped>
/* nút tên đã bỏ — menu tự đẩy sát phải */
.layout-topbar-menu {
  margin-left: auto !important;
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
/* nút reset trong header settings: đẩy sát nút close, cùng style icon */
.user-dialog .settings-reset-icon {
  margin-left: auto;
  margin-right: 0.5rem;
  width: 2rem;
  height: 2rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 50%;
  background: transparent;
  color: var(--text-color-secondary);
  cursor: pointer;
}
.user-dialog .settings-reset-icon:hover:not(:disabled) {
  background: var(--surface-hover);
  color: var(--text-color);
}
.user-dialog .settings-reset-icon:disabled {
  opacity: 0.5;
  cursor: default;
}
</style>
