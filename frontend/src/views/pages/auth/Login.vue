<script setup>
import { useLayout } from "@/layout/composables/layout";
import { ref, computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import { useToast } from "primevue/usetoast";
import AppConfig from "@/layout/AppConfig.vue";

const REMEMBER_KEY = "tfs_remember_username";

const { layoutConfig } = useLayout();
const router = useRouter();
const toast = useToast();

const username = ref("");
const password = ref("");
const remember = ref(false);
const loading = ref(false);
const errorMsg = ref("");
const submitted = ref(false);

const logoUrl = computed(() => {
    return `/layout/images/${layoutConfig.darkTheme.value ? 'logo-white' : 'logo-dark'}.svg`;
});

const usernameInvalid = computed(
  () => submitted.value && !username.value.trim(),
);
const passwordInvalid = computed(() => submitted.value && !password.value);

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
  if (usernameInvalid.value || passwordInvalid.value) return;
  loading.value = true;
  errorMsg.value = "";
  try {
    const r = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user: username.value.trim(),
        password: password.value,
        remember: remember.value,
      }),
    });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.error || "Lỗi đăng nhập");
    if (remember.value) {
      localStorage.setItem(REMEMBER_KEY, username.value.trim());
    } else {
      localStorage.removeItem(REMEMBER_KEY);
    }
    toast.add({
      severity: "success",
      summary: "Đăng nhập thành công",
      detail: `Xin chào ${j.fullname || j.user || username.value.trim()}!`,
      life: 3000,
    });
    await router.push("/");
  } catch (e) {
    errorMsg.value = e.message;
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
            </div>
            <div v-if="errorMsg">
              <InlineMessage
                severity="error"
                class="w-full justify-content-start"
                >{{ errorMsg }}</InlineMessage
              >
            </div>

            <div class="flex align-items-center mt-2">
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
              class="w-full p-3 text-xl mt-4"></Button>
          </form>
        </div>
      </div>
    </div>
  </div>
  <AppConfig simple />
</template>

<style scoped>
.pi-eye {
  transform: scale(1.6);
  margin-right: 1rem;
}

.pi-eye-slash {
  transform: scale(1.6);
  margin-right: 1rem;
}
</style>
