import axiosInstance from '@/lib/axios'
import {
    FileStructure,
    FileListResponse,
    FileContentResponse,
    FileRenameRequest,
    FileMoveRequest,
    FileCopyRequest,
    FileSearchRequest
} from '@/typings/file'

class FileService {
    async getFiles(): Promise<FileStructure[]> {
        const response =
            await axiosInstance.post<FileListResponse>('/agent/files')
        return response.data.files
    }

    async getFileContent(path: string): Promise<FileContentResponse> {
        const response = await axiosInstance.post<FileContentResponse>(
            '/agent/files/content',
            { path }
        )
        return response.data
    }

    async saveFileContent(path: string, content: string): Promise<void> {
        await axiosInstance.post('/agent/files/save', { path, content })
    }

    async createFile(path: string, content = ''): Promise<void> {
        await axiosInstance.post('/agent/files/create', { path, content })
    }

    async createFolder(path: string): Promise<void> {
        await axiosInstance.post('/agent/files/create-folder', { path })
    }

    async deleteFile(path: string): Promise<void> {
        await axiosInstance.delete('/agent/files', { data: { path } })
    }

    async renameFile(data: FileRenameRequest): Promise<void> {
        await axiosInstance.post('/agent/files/rename', data)
    }

    async moveFile(data: FileMoveRequest): Promise<void> {
        await axiosInstance.post('/agent/files/move', data)
    }

    async copyFile(data: FileCopyRequest): Promise<void> {
        await axiosInstance.post('/agent/files/copy', data)
    }

    async searchFiles(data: FileSearchRequest): Promise<FileStructure[]> {
        const response = await axiosInstance.post<FileListResponse>(
            '/agent/files/search',
            data
        )
        return response.data.files
    }
}

export const fileService = new FileService()
