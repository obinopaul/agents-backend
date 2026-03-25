import { ACCESS_TOKEN } from '@/constants/auth'
import axios from 'axios'

const axiosInstance = axios.create({
    baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
    headers: {
        'Content-Type': 'application/json'
    }
})

axiosInstance.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem(ACCESS_TOKEN)
        if (token) {
            config.headers.Authorization = `Bearer ${token}`
        }
        return config
    },
    (error) => {
        return Promise.reject(error)
    }
)

// Add flag to prevent multiple refresh loops
let isRefreshing = false
let failedQueue: any[] = []

const processQueue = (error: any, token: string | null = null) => {
    failedQueue.forEach(prom => {
        if (error) {
            prom.reject(error)
        } else {
            prom.resolve(token)
        }
    })
    failedQueue = []
}

axiosInstance.interceptors.response.use(
    (response) => {
        return response
    },
    async (error) => {
        const originalRequest = error.config
        
        if (error.response?.status === 401 && !originalRequest._retry) {
            if (isRefreshing) {
                return new Promise(function(resolve, reject) {
                    failedQueue.push({resolve, reject})
                }).then(token => {
                    originalRequest.headers['Authorization'] = 'Bearer ' + token
                    return axiosInstance(originalRequest)
                }).catch(err => {
                    return Promise.reject(err)
                })
            }

            originalRequest._retry = true
            isRefreshing = true

            try {
                // Call refresh endpoint (uses HttpOnly cookie)
                // Note: The backend refresh endpoint needs to be called. 
                // We use axios directly to avoid this interceptor loop.
                const { data } = await axios.post(
                   import.meta.env.VITE_API_URL + '/api/v1/auth/refresh',
                   {}, 
                   { withCredentials: true }
                )
                
                if (data?.code === 200 && data?.data?.access_token) {
                    const newToken = data.data.access_token
                    localStorage.setItem(ACCESS_TOKEN, newToken)
                    axiosInstance.defaults.headers.common['Authorization'] = 'Bearer ' + newToken
                    originalRequest.headers['Authorization'] = 'Bearer ' + newToken
                    processQueue(null, newToken)
                    return axiosInstance(originalRequest)
                }
            } catch (err) {
                 processQueue(err, null)
                 localStorage.removeItem(ACCESS_TOKEN)
                 // Don't redirect to login if we're on a share route
                 if (!window.location.pathname.startsWith('/share/')) {
                     window.location.href = '/login'
                 }
            } finally {
                isRefreshing = false
            }
        }
        return Promise.reject(error)
    }
)

export default axiosInstance
