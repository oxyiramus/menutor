<script setup lang="ts">
import { onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppSidebar from '@/components/layout/AppSidebar.vue'
import MobileBottomNav from '@/components/layout/MobileBottomNav.vue'
import ToastNotification from '@/components/ui/ToastNotification.vue'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const auth = useAuthStore()
const router = useRouter()

watch(() => auth.isAuthenticated, (authenticated) => {
  if (!authenticated && !route.meta.public) void router.replace('/login')
})

onMounted(() => auth.init())
</script>

<template>
  <div v-if="route.meta.public" class="h-screen bg-gray-50">
    <RouterView />
    <ToastNotification />
  </div>
  <div v-else-if="auth.isAuthenticated" class="flex h-[100dvh] bg-gray-50">
    <AppSidebar />
    <main class="flex-1 overflow-y-auto pb-20 lg:pb-0 overscroll-contain">
      <div class="h-full">
        <RouterView />
      </div>
    </main>
    <MobileBottomNav />
    <ToastNotification />
  </div>
</template>
