import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react'
import type {
    BaseQueryFn,
    FetchArgs,
    FetchBaseQueryError
} from '@reduxjs/toolkit/query'
import type { CreditBalanceResponse, CreditUsageResponse } from '@/typings/user'
import { ACCESS_TOKEN } from '@/constants/auth'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

/**
 * Backend response wrapper type.
 * All backend responses are wrapped in { code, data, msg } format.
 */
interface BackendResponse<T> {
    code: number
    data: T
    msg: string
}

const baseQuery = fetchBaseQuery({
    baseUrl: API_URL,
    prepareHeaders: (headers) => {
        const token = localStorage.getItem(ACCESS_TOKEN)
        if (token) {
            headers.set('Authorization', `Bearer ${token}`)
        }
        headers.set('Content-Type', 'application/json')
        return headers
    }
})

const baseQueryWithReauth: BaseQueryFn<
    string | FetchArgs,
    unknown,
    FetchBaseQueryError
> = async (args, api, extraOptions) => {
    const result = await baseQuery(args, api, extraOptions)
    if (result.error && result.error.status === 401) {
        localStorage.removeItem(ACCESS_TOKEN)
        // Don't redirect to login if we're on a share route
        if (!window.location.pathname.startsWith('/share/')) {
            window.location.href = '/login'
        }
    }
    return result
}

export const userApi = createApi({
    reducerPath: 'userApi',
    baseQuery: baseQueryWithReauth,
    tagTypes: ['CreditBalance', 'CreditUsage'],
    endpoints: (builder) => ({
        getCreditBalance: builder.query<CreditBalanceResponse, void>({
            query: () => '/agent/credits/balance',
            transformResponse: (
                response: BackendResponse<CreditBalanceResponse> | CreditBalanceResponse
            ) => {
                // Handle wrapped response from backend
                if ('data' in response && response.data) {
                    return response.data as CreditBalanceResponse
                }
                return response as CreditBalanceResponse
            },
            providesTags: ['CreditBalance']
        }),
        getCreditUsage: builder.query<
            CreditUsageResponse,
            { page: number; perPage: number }
        >({
            query: ({ page, perPage }) => ({
                url: '/agent/credits/usage',
                params: { page, per_page: perPage }
            }),
            transformResponse: (
                response: BackendResponse<CreditUsageResponse> | CreditUsageResponse
            ) => {
                // Handle wrapped response from backend
                if ('data' in response && response.data) {
                    return response.data as CreditUsageResponse
                }
                return response as CreditUsageResponse
            },
            providesTags: ['CreditUsage']
        })
    })
})

export const { useGetCreditBalanceQuery, useGetCreditUsageQuery } = userApi
