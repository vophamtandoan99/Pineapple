<script setup>
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";
import { useToast } from "primevue/usetoast";
import { useAuth } from "@/service/AuthService";
import { useProject } from "@/service/ProjectService";
import AppConfig from "@/layout/AppConfig.vue";
import PickerArea from "@/components/PickerArea.vue";

const router = useRouter();
const toast = useToast();
const { fullname, clearUser } = useAuth();
const {
  collections,
  projects,
  currentCollection,
  loadCollections,
  loadProjects,
  selectProject,
} = useProject();

// Stepper PrimeVue: 0 = collection, 1 = project
const activeStep = ref(0);
const loading = ref(true);
const errorMsg = ref("");
const picking = ref("");
const loggingOut = ref(false);

// Vòng lặp màu/icon như các hàng ở trang NotFound
const STYLES = [
  { icon: "pi-th-large", bg: "bg-cyan-400" },
  { icon: "pi-briefcase", bg: "bg-orange-400" },
  { icon: "pi-folder", bg: "bg-indigo-400" },
  { icon: "pi-database", bg: "bg-teal-400" },
  { icon: "pi-cog", bg: "bg-purple-400" },
  { icon: "pi-box", bg: "bg-blue-400" },
];
const styleAt = (i) => STYLES[i % STYLES.length];
const subtitle = (p) =>
  p.description || (p.state ? `Trạng thái: ${p.state}` : "Dự án TFS");

onMounted(async () => {
  const res = await loadCollections();
  loading.value = false;
  if (!res.ok) {
    errorMsg.value = res.error || "Không tải được danh sách collection.";
  }
});

async function pickCollection(c) {
  if (loading.value) return;
  currentCollection.value = c.name;
  loading.value = true;
  errorMsg.value = "";
  const res = await loadProjects(c.name, true);
  loading.value = false;
  if (!res.ok) {
    errorMsg.value = res.error || "Không tải được danh sách dự án.";
    return;
  }
  // Fetch OK (kể cả 0 project) → chuyển sang bước 2; empty hiển thị trong panel 2
  activeStep.value = 1;
}

function backToCollections() {
  activeStep.value = 0;
  errorMsg.value = "";
}

async function pickProject(p) {
  if (picking.value) return;
  picking.value = p.name;
  try {
    await selectProject(currentCollection.value, p.name);
    toast.add({
      severity: "success",
      summary: "Đã chọn dự án",
      detail: `${currentCollection.value} / ${p.name}`,
      life: 2000,
    });
    router.push("/");
  } catch (e) {
    toast.add({
      severity: "error",
      summary: "Lỗi chọn dự án",
      detail: e.message,
      life: 4000,
    });
    picking.value = "";
  }
}

function retry() {
  loading.value = true;
  errorMsg.value = "";
  const p =
    activeStep.value === 0
      ? loadCollections(true)
      : loadProjects(currentCollection.value, true);
  p.then((res) => {
    if (!res.ok) errorMsg.value = res.error || "Không tải được.";
  }).finally(() => {
    loading.value = false;
  });
}

async function logout() {
  if (loggingOut.value) return;
  loggingOut.value = true;
  try {
    await fetch("/api/logout", { method: "POST" });
  } catch {
    /* vẫn logout local kể cả khi server lỗi */
  }
  clearUser();
  router.push("/auth/login");
}
</script>

<template>
  <div
    class="surface-ground flex align-items-center justify-content-center h-screen min-w-screen overflow-hidden">
    <div
      class="flex flex-column align-items-center justify-content-center w-full max-h-full">
      <div
        class="max-h-full"
        style="
          width: min(40rem, 100%);
          border-radius: 56px;
          padding: 0.3rem;
          background: linear-gradient(
            180deg,
            var(--primary-color) 10%,
            rgba(33, 150, 243, 0) 30%
          );
        ">
        <div
          class="surface-card w-full py-4 px-4 sm:px-8 flex flex-column align-items-center justify-content-center min-h-0 overflow-hidden"
          style="border-radius: 53px; height: min(80vh, calc(100vh - 2.5rem))">
          <img
            src="/layout/images/pinia-course.png"
            alt="logo"
            class="w-10rem flex-shrink-0 mb-4" />

          <Stepper
            v-model:activeStep="activeStep"
            class="stepper w-full flex-1 min-h-0">
            <StepperPanel header="Collection">
              <template #header="{ active, clickCallback }">
                <span
                  class="step-head flex align-items-center justify-content-center gap-1 cursor-pointer"
                  @click="clickCallback">
                  <img
                    v-if="active"
                    src="/layout/images/logo-light.svg"
                    alt=""
                    class="w-2rem h-2rem flex-shrink-0 mb-2 rotate-12 cursor-pointer" />
                  <span
                    v-else
                    class="step-num cursor-pointer flex align-items-center justify-content-center border-circle flex-shrink-0">
                    1
                  </span>
                  <span
                    :class="active ? 'font-semibold text-900' : 'text-500'"
                    class="cursor-pointer"
                    >Bộ sưu tập</span
                  >
                </span>
              </template>
              <div
                class="scroll-list w-full flex-1 min-h-0 overflow-y-auto overflow-x-hidden flex flex-column align-items-center px-1">
                <PickerArea
                  :loading="loading"
                  :error="errorMsg"
                  :rows="collections"
                  :is-project="false"
                  :picking="picking"
                  :style-at="styleAt"
                  :row-subtitle="() => 'Project Collection'"
                  empty-text="Không có collection nào."
                  @pick="pickCollection"
                  @retry="retry" />
              </div>
            </StepperPanel>

            <StepperPanel header="Dự án">
              <template #header="{ active, clickCallback }">
                <span
                  class="step-head flex align-items-center justify-content-center gap-1 cursor-pointer"
                  :class="{
                    'opacity-50 cursor-not-allowed': !currentCollection,
                  }"
                  :title="!currentCollection ? 'Chọn collection trước' : ''"
                  @click="currentCollection && clickCallback($event)">
                  <img
                    v-if="active"
                    src="/layout/images/logo-light.svg"
                    alt=""
                    class="w-2rem h-2rem flex-shrink-0 mb-2 rotate-12 cursor-pointer" />
                  <span
                    v-else
                    class="step-num cursor-pointer flex align-items-center justify-content-center border-circle flex-shrink-0">
                    2
                  </span>
                  <span
                    :class="active ? 'font-semibold text-900' : 'text-500'"
                    class="cursor-pointer"
                    >Dự án</span
                  >
                </span>
              </template>
              <div class="panel-col w-full h-full flex flex-column min-h-0">
                <div
                  class="scroll-list w-full flex-1 min-h-0 overflow-y-auto overflow-x-hidden flex flex-column align-items-center px-1">
                  <PickerArea
                    :loading="loading"
                    :error="errorMsg"
                    :rows="projects"
                    :is-project="true"
                    :picking="picking"
                    :style-at="styleAt"
                    :row-subtitle="subtitle"
                    empty-text="Collection không có dự án."
                    @pick="pickProject"
                    @retry="retry" />
                </div>

                <!-- nút đổi collection: dưới cùng panel -->
                <div class="w-full text-center pt-5 flex-shrink-0">
                  <Button severity="secondary" @click="backToCollections">
                    <i class="pi pi-arrow-left mr-2 text-base"></i>
                    Đổi bộ sưu tập
                  </Button>
                </div>
              </div>
            </StepperPanel>
          </Stepper>

          <div
            class="text-500 text-sm pt-2 mt-1 text-center border-top-1 border-primary-200 flex-shrink-0 w-full">
            Xin chào {{ fullname || "bạn" }} - Tiện ích sẽ tải theo dự án bạn
            chọn.
          </div>
          <div class="mt-2 flex-shrink-0 flex justify-content-center">
            <Button
              label="Đăng xuất"
              icon="pi pi-sign-out"
              severity="secondary"
              text
              size="small"
              :loading="loggingOut"
              @click="logout" />
          </div>
        </div>
      </div>
    </div>
  </div>
  <AppConfig simple />
</template>

<style scoped>
/* Stepper chiếm phần còn lại của card, content panel scroll riêng — card không vượt 100vh */
:deep(.p-stepper) {
  display: flex;
  flex-direction: column;
  min-height: 0;
}
:deep(.p-stepper-nav) {
  flex-shrink: 0;
}
/* Panels co giãn theo card (card height cố định) — không vượt, không cần scroll card */
:deep(.p-stepper-panels) {
  display: flex;
  flex-direction: column;
  flex: 1 1 auto;
  min-height: 0;
}
:deep(.p-stepper-content) {
  display: flex;
  flex-direction: column;
  flex: 1 1 auto;
  min-height: 0;
}
:deep(.p-stepper-content > .p-stepper-panel) {
  display: flex;
  flex-direction: column;
  flex: 1 1 auto;
  min-height: 0;
}

/* Step chưa active: số tròn nhỏ thay vì logo */
.step-num {
  width: 1.5rem;
  height: 1.5rem;
  font-size: 0.75rem;
  color: var(--text-color-secondary);
  border: 1px solid var(--surface-border);
}

/* Row cuối trong vùng scroll không cần gạch chân */
.scroll-list :deep(button:last-of-type) {
  border-bottom: 0;
}
</style>
