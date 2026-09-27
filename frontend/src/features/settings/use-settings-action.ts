import { useMutation, useQueryClient } from '@tanstack/react-query'
import { sessionQueryKey } from '@/api/auth'
import { apiRequest, type ApiError } from '@/api/request'
import { settingsKey, settingsPath } from '@/api/settings'

export function useSettingsAction<T = void>(workspaceId: string) {
  const cache = useQueryClient()
  return useMutation<T, ApiError, { path: string; body: unknown }>({
    mutationFn: ({ path, body }) =>
      apiRequest<T>(settingsPath(workspaceId, path), body),
    onSettled: async () => {
      await Promise.all([
        cache.invalidateQueries({ queryKey: settingsKey(workspaceId) }),
        cache.invalidateQueries({ queryKey: sessionQueryKey }),
      ])
    },
  })
}
