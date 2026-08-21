<script setup>
import { useLayout } from "@/layout/composables/layout";
import { ref, computed, onMounted, watch } from "vue";
import { useRouter } from "vue-router";
import { useToast } from "primevue/usetoast";
import AppConfig from "@/layout/AppConfig.vue";

const REMEMBER_KEY = "tfs_remember_username";

const { layoutConfig } = useLayout();
const router = useRouter();
const toast = useToast();

const username = ref("");
const password = ref("");
const token = ref("");
const collection = ref("");
const authMode = ref("token");
const authOptions = [
  { label: "Token", value: "token" },
  { label: "Mật khẩu", value: "password" },
];
const remember = ref(false);
const loading = ref(false);
const submitted = ref(false);

const logoUrl = computed(() => {
    return `/layout/images/${layoutConfig.darkTheme.value ? 'logo-light' : 'logo-dark'}.svg`;
});

const usernameInvalid = computed(
  () => submitted.value && authMode.value === "password" && !username.value.trim(),
);
const passwordInvalid = computed(
  () => submitted.value && authMode.value === "password" && !password.value,
);
const tokenInvalid = computed(
  () => submitted.value && authMode.value === "token" && !token.value.trim(),
);

// Đổi tab: reset validate của tab trước
watch(authMode, () => {
  submitted.value = false;
});

onMounted(() => {
  const saved = localStorage.getItem(REMEMBER_KEY);
  if (saved) {
    username.value = saved;
    remember.value = true;
  }
});

async function login() {
  if (loading.value) return;
  submitted.value = true;
  if (usernameInvalid.value || passwordInvalid.value || tokenInvalid.value) return;
  loading.value = true;
  const payload =
    authMode.value === "token"
      ? {
          token: token.value.trim(),
          collection: collection.value.trim(),
          remember: remember.value,
        }
      : {
          user: username.value.trim(),
          password: password.value,
          remember: remember.value,
        };
  try {
    const r = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.error || "Lỗi đăng nhập");
    if (authMode.value === "password" && remember.value) {
      localStorage.setItem(REMEMBER_KEY, username.value.trim());
    } else {
      localStorage.removeItem(REMEMBER_KEY);
    }
    toast.add({
      severity: "success",
      summary: "Đăng nhập thành công",
      detail: `Xin chào ${j.fullname || j.user || "bạn"}!`,
      life: 3000,
    });
    await router.push("/");
  } catch (e) {
    // Lỗi từ server hiển thị qua toast — text dài tự wrap, không tràn form
    toast.add({
      severity: "error",
      summary: "Đăng nhập thất bại",
      detail: e.message,
      life: 6000,
    });
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div
    class="surface-ground py-4 flex align-items-center justify-content-center h-screen min-w-screen overflow-hidden">
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
          class="surface-card w-full py-6 px-5 sm:px-8 flex flex-column justify-content-center overflow-y-auto"
          style="
            border-radius: 53px;
            height: min(80vh, calc(100vh - 2.5rem));
          ">
          <div class="text-center mb-5">
            <img :src="logoUrl" alt="Sakai logo" class="mb-3 w-3rem flex-shrink-0" />
            <div class="text-900 text-3xl font-medium mb-3">Chào mừng!</div>
            <span class="text-600 font-medium">Đăng nhập để tiếp tục</span>
          </div>

          <form @submit.prevent="login" class="w-full flex flex-column gap-3">
            <div class="flex justify-content-center">
              <SelectButton
                v-model="authMode"
                :options="authOptions"
                optionLabel="label"
                optionValue="value"
                class="auth-toggle" />
            </div>

            <template v-if="authMode === 'password'">
              <div class="flex flex-column gap-2">
                <label
                  for="username1"
                  class="block text-900 text-xl font-medium"
                  >Tài khoản</label
                >
                <InputText
                  id="username1"
                  type="text"
                  placeholder="Tài khoản"
                  autocomplete="username"
                  :class="[
                    'w-full mb-1',
                    { 'p-invalid': usernameInvalid },
                  ]"
                  style="padding: 1rem"
                  v-model="username" />
                <small v-if="usernameInvalid" class="block p-error"
                  >Tài khoản là bắt buộc</small
                >
                <!-- Reserve 1 dòng hint để chiều cao khớp tab Token (chống nhảy UI) -->
                <small v-else class="block text-600" style="visibility: hidden"
                  >placeholder</small
                >
              </div>

              <div class="flex flex-column gap-2">
                <label for="password1" class="block text-900 font-medium text-xl"
                  >Mật khẩu</label
                >
                <Password
                  id="password1"
                  v-model="password"
                  placeholder="Mật khẩu"
                  autocomplete="current-password"
                  :toggleMask="true"
                  :feedback="false"
                  :class="['w-full', { 'p-invalid': passwordInvalid }]"
                  :inputClass="['w-full', { 'p-invalid': passwordInvalid }]"
                  :inputStyle="{ padding: '1rem' }"></Password>
                <small v-if="passwordInvalid" class="block p-error"
                  >Mật khẩu là bắt buộc</small
                >
                <small v-else class="block text-600" style="visibility: hidden"
                  >placeholder</small
                >
              </div>
            </template>

            <template v-else>
              <div class="flex flex-column gap-2">
                <label
                  for="collection1"
                  class="block text-900 font-medium text-xl"
                  >Collection</label
                >
                <InputText
                  id="collection1"
                  type="text"
                  placeholder="Bỏ trống nếu dùng collection mặc định"
                  autocomplete="off"
                  class="w-full mb-1"
                  style="padding: 1rem"
                  v-model="collection" />
                <!-- Giữ 1 dòng ẩn để chiều cao khớp tab Mật khẩu (chống nhảy UI) -->
                <small class="block text-600" style="visibility: hidden"
                  >placeholder</small
                >
              </div>

              <div class="flex flex-column gap-2">
                <label for="token1" class="block text-900 font-medium text-xl"
                  >Personal Access Token</label
                >
              <Password
                id="token1"
                v-model="token"
                placeholder="Dán PAT từ TFS"
                autocomplete="off"
                :toggleMask="true"
                :feedback="false"
                :class="['w-full', { 'p-invalid': tokenInvalid }]"
                :inputClass="['w-full', { 'p-invalid': tokenInvalid }]"
                :inputStyle="{ padding: '1rem' }"></Password>
              <small v-if="tokenInvalid" class="block p-error"
                >Token là bắt buộc</small
              >
              <small v-else class="text-600"
                >Tạo ở TFS: User settings, Personal access tokens</small
              >
              </div>
            </template>

            <div class="flex align-items-center mt-auto">
              <Checkbox
                v-model="remember"
                inputId="remember1"
                binary
                class="mr-2" />
              <label for="remember1" class="text-600 cursor-pointer"
                >Ghi nhớ đăng nhập</label
              >
            </div>

            <Button
              :label="loading ? 'Đang đăng nhập...' : 'Đăng nhập'"
              type="submit"
              :loading="loading"
              class="login-btn w-full p-3 text-xl mt-4"></Button>
          </form>
        </div>
      </div>
    </div>
  </div>
  <AppConfig simple />
</template>

<style scoped>
/* Icon mắt đặt bên TRÁI input — mép phải chừa trống cho icon password
   manager (Passbolt...) của extension chèn vào, hết đè nhau.
   PrimeVue 3.49: icon là SVG .p-input-icon, absolute right: 0.75rem —
   đổi sang left. padding-left !important để thắng inline inputStyle. */
:deep(.p-password > .p-input-icon) {
  left: 1.25rem;
  right: auto;
  transform: scale(1.6);
  opacity: 0.7;
}

:deep(.p-password input) {
  padding-left: 3rem !important;
}

/* 2 nút Token / Mật khẩu cùng độ rộng */
:deep(.auth-toggle .p-button) {
  min-width: 10rem;
  justify-content: center;
}

/* Nút login: label luôn căn giữa (label flex 1 1 auto mặc định sẽ dạt trái) */
:deep(.login-btn) {
  justify-content: center;
}

:deep(.login-btn .p-button-label) {
  flex: 0 1 auto;
}

:deep(.login-btn .p-button-loading-icon) {
  margin-right: 0.5rem;
}
</style>

<style>
/* Icon Passbolt chèn vào DOM trang dưới dạng <passbolt-iframe> — ẩn luôn
   cho sạch. Element ngoài #app nên block này PHẢI không scoped.
   Các extension khác icon nằm mép phải input, đã chừa trống sau khi
   chuyển icon mắt sang trái. */
passbolt-iframe {
  display: none !important;
}
</style>
