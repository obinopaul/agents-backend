import { useState, useRef, useEffect } from 'react';
import { File, Plus, Trash2, FileText, Image, Book, X, Upload, ChevronRight, FolderOpen, Folder, RefreshCw } from 'lucide-react';
import { useEditorStore, ProjectFile } from '../store/editorStore';
import { workspaceService } from '../services/workspaceService';

export default function FileManager() {
  const { 
    projectFiles, 
    setProjectFiles,
    removeProjectFile, 
    currentFile, 
    setCurrentFile,
    currentDocument,
    setCurrentDocument,
  } = useEditorStore();
  
  const [isOpen, setIsOpen] = useState(true);
  const [showAddMenu, setShowAddMenu] = useState(false);
  const [newFileName, setNewFileName] = useState('');
  const [newFileType, setNewFileType] = useState<'tex' | 'bib' | 'image' | 'other'>('tex');
  const [imagePreview, setImagePreview] = useState<{ name: string; content: string } | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [documents, setDocuments] = useState<{ name: string; file_count: number }[]>([]);
  const [showDocumentSelector, setShowDocumentSelector] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Load documents from workspace on mount
  useEffect(() => {
    if (workspaceService.isWorkspaceMode()) {
      loadDocuments();
    }
  }, []);

  // Load files when document changes
  useEffect(() => {
    if (workspaceService.isWorkspaceMode() && currentDocument) {
      loadDocumentFiles(currentDocument);
    }
  }, [currentDocument]);

  const loadDocuments = async () => {
    setIsLoading(true);
    try {
      const docs = await workspaceService.listDocuments();
      setDocuments(docs.map((name: string) => ({ name, file_count: 0 })));
      
      // If no document selected and documents exist, select first one
      if (!currentDocument && docs.length > 0) {
        setCurrentDocument(docs[0]);
      }
    } catch (error) {
      console.error('Failed to load documents:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const loadDocumentFiles = async (docName: string) => {
    setIsLoading(true);
    try {
      const files = await workspaceService.listFiles(docName);
      const projectFiles: ProjectFile[] = files.map((f: any) => ({
        name: f.name,
        content: '', // Content loaded on demand
        type: f.type,
      }));
      setProjectFiles(projectFiles);
      
      // Select first .tex file if available
      const firstTexFile = projectFiles.find(f => f.type === 'tex');
      if (firstTexFile && !currentFile) {
        setCurrentFile(firstTexFile.name);
      }
    } catch (error) {
      console.error('Failed to load files:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const getFileIcon = (type: string, isExpanded?: boolean) => {
    switch (type) {
      case 'folder':
        return isExpanded ? <FolderOpen className="w-4 h-4 text-blue-400" /> : <Folder className="w-4 h-4 text-blue-400" />;
      case 'tex':
        return <FileText className="w-4 h-4 text-blue-400" />;
      case 'bib':
        return <Book className="w-4 h-4 text-green-400" />;
      case 'image':
        return <Image className="w-4 h-4 text-purple-400" />;
      default:
        return <File className="w-4 h-4 text-gray-400" />;
    }
  };

  const handleAddFile = async () => {
    if (!newFileName.trim() || !currentDocument) return;

    let fileName = newFileName.trim();
    
    // Add appropriate extension if not present
    if (newFileType === 'tex' && !fileName.endsWith('.tex')) {
      fileName += '.tex';
    } else if (newFileType === 'bib' && !fileName.endsWith('.bib')) {
      fileName += '.bib';
    }

    // Check if file already exists
    if (projectFiles.some(f => f.name === fileName)) {
      alert('File already exists!');
      return;
    }

    // In workspace mode, create file via API
    if (workspaceService.isWorkspaceMode()) {
      const defaultContent = newFileType === 'bib' 
        ? '@article{example,\n  title={Example},\n  author={Author},\n  year={2024}\n}' 
        : '';
      const success = await workspaceService.writeFile(currentDocument, fileName, defaultContent);
      if (success) {
        await loadDocumentFiles(currentDocument);
        setCurrentFile(fileName);
      }
    } else {
      // Fallback to local store
      const newFile: ProjectFile = {
        name: fileName,
        content: newFileType === 'bib' ? '@article{example,\n  title={Example},\n  author={Author},\n  year={2024}\n}' : '',
        type: newFileType
      };
      setProjectFiles([...projectFiles, newFile]);
      setCurrentFile(fileName);
    }

    setNewFileName('');
    setShowAddMenu(false);
  };

  const handleImageUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files || files.length === 0) return;

    Array.from(files).forEach(file => {
      // Check if image already exists
      if (projectFiles.some(f => f.name === file.name)) {
        alert(`Image ${file.name} already exists!`);
        return;
      }

      const reader = new FileReader();
      reader.onload = async (e) => {
        const base64 = e.target?.result as string;
        // Remove data URL prefix
        const base64Data = base64.split(',')[1];
        
        if (workspaceService.isWorkspaceMode() && currentDocument) {
          // Save via API (binary files need special handling)
          // For now, just refresh the file list
          await loadDocumentFiles(currentDocument);
        } else {
          setProjectFiles([...projectFiles, {
            name: file.name,
            content: base64Data,
            type: 'image'
          }]);
        }
      };
      reader.readAsDataURL(file);
    });

    // Reset input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleFileClick = (fileName: string) => {
    const file = projectFiles.find(f => f.name === fileName);
    
    // If it's an image, show preview modal instead of editing
    if (file && file.type === 'image') {
      setImagePreview({ name: fileName, content: file.content });
      return;
    }
    
    // Set the current file - the Editor will handle loading the content
    setCurrentFile(fileName);
  };

  const handleDeleteFile = async (fileName: string) => {
    // In workspace mode, this just removes from local state
    // Actual file deletion would need an API endpoint
    removeProjectFile(fileName);
    if (currentFile === fileName) {
      const remaining = projectFiles.filter(f => f.name !== fileName);
      const firstTex = remaining.find(f => f.type === 'tex');
      setCurrentFile(firstTex?.name || '');
    }
  };

  // No document selected - show document selector
  if (!currentDocument && workspaceService.isWorkspaceMode()) {
    return (
      <div className="h-full flex flex-col bg-gray-900 border-r border-gray-700" style={{ width: '250px' }}>
        <div className="px-3 py-2 bg-gray-800 border-b border-gray-700">
          <div className="flex items-center justify-between mb-1">
            <h3 className="text-sm font-semibold text-gray-300">Documents</h3>
            <button
              onClick={loadDocuments}
              className="p-1 rounded hover:bg-gray-700 text-gray-400 hover:text-white transition-colors"
              title="Refresh"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto text-sm p-2">
          {isLoading ? (
            <div className="text-gray-500 text-center py-8">Loading...</div>
          ) : documents.length === 0 ? (
            <div className="text-gray-500 text-center py-8">
              <FolderOpen className="w-12 h-12 mx-auto mb-2 opacity-50" />
              <p className="text-xs">No documents found</p>
              <p className="text-xs mt-2 text-gray-600">
                Use document_template_init to create a document
              </p>
            </div>
          ) : (
            documents.map((doc) => (
              <button
                key={doc.name}
                onClick={() => setCurrentDocument(doc.name)}
                className="w-full px-3 py-2 mb-1 rounded flex items-center gap-2 hover:bg-gray-800 transition-colors text-left"
              >
                <FolderOpen className="w-4 h-4 text-blue-400" />
                <span className="text-gray-300 truncate">{doc.name}</span>
              </button>
            ))
          )}
        </div>
      </div>
    );
  }

  if (!isOpen) {
    return (
      <div className="h-full bg-gray-900 border-r border-gray-700 flex flex-col items-center py-2 w-12">
        <button
          onClick={() => setIsOpen(true)}
          className="p-2 rounded hover:bg-gray-800 text-gray-400 hover:text-white transition-colors"
          title="Open file explorer"
        >
          <ChevronRight className="w-5 h-5" />
        </button>
        <div className="mt-4 flex flex-col gap-2">
          <div className="w-6 h-6 flex items-center justify-center">
            <FileText className="w-4 h-4 text-blue-400" />
          </div>
          <div className="w-6 h-6 flex items-center justify-center">
            <Image className="w-4 h-4 text-purple-400" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-gray-900 border-r border-gray-700" style={{ width: '250px' }}>
      {/* Header */}
      <div className="px-3 py-2 bg-gray-800 border-b border-gray-700">
        <div className="flex items-center justify-between mb-1">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setIsOpen(false)}
              className="p-1 rounded hover:bg-gray-700 text-gray-400 hover:text-white transition-colors"
              title="Close file explorer"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
            <h3 className="text-sm font-semibold text-gray-300">Files</h3>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={() => loadDocumentFiles(currentDocument)}
              className="p-1 rounded hover:bg-gray-700 text-gray-400 hover:text-white transition-colors"
              title="Refresh files"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            </button>
            <button
              onClick={() => setShowAddMenu(true)}
              className="p-1 rounded hover:bg-gray-700 text-gray-400 hover:text-white transition-colors"
              title="Add file"
            >
              <Plus className="w-4 h-4" />
            </button>
          </div>
        </div>
        {currentDocument && (
          <button
            onClick={() => setShowDocumentSelector(true)}
            className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1"
          >
            <FolderOpen className="w-3 h-3" />
            {currentDocument}
          </button>
        )}
        <div className="text-xs text-gray-500 flex items-center gap-1 mt-1">
          <span>Editing:</span>
          <span className="text-blue-400 font-medium">{currentFile || 'None'}</span>
        </div>
      </div>

      {/* Files List */}
      <div className="flex-1 overflow-y-auto text-sm">
        {isLoading ? (
          <div className="text-gray-500 text-center py-8">Loading...</div>
        ) : projectFiles.length === 0 ? (
          <div className="px-3 py-8 text-center text-gray-500 text-xs">
            <File className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p>No files in document</p>
            <p className="text-xs mt-1">Click + to add files</p>
          </div>
        ) : (
          projectFiles.map((file) => (
            <div
              key={file.name}
              className={`group flex items-center gap-2 px-3 py-1.5 hover:bg-gray-800 transition-colors ${
                currentFile === file.name ? 'bg-gray-800 border-l-2 border-blue-500' : ''
              }`}
            >
              <button
                onClick={() => handleFileClick(file.name)}
                className="flex items-center gap-2 flex-1 text-left min-w-0"
              >
                {getFileIcon(file.type)}
                <span className="text-gray-300 text-xs truncate">{file.name}</span>
              </button>
              <button
                onClick={() => handleDeleteFile(file.name)}
                className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-gray-700 text-gray-400 hover:text-red-400 transition-all"
                title="Remove file"
              >
                <Trash2 className="w-3 h-3" />
              </button>
            </div>
          ))
        )}
      </div>

      {/* Add File Dialog */}
      {showAddMenu && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-gray-800 rounded-lg border border-gray-700 p-4 w-full max-w-md">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-white">Add File</h3>
              <button
                onClick={() => {
                  setShowAddMenu(false);
                  setNewFileName('');
                }}
                className="p-1 rounded hover:bg-gray-700 text-gray-400"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3">
              {/* File Type Selection */}
              <div>
                <label className="block text-sm text-gray-300 mb-2">File Type</label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    onClick={() => setNewFileType('tex')}
                    className={`px-3 py-2 rounded flex items-center gap-2 text-sm transition-colors ${
                      newFileType === 'tex' 
                        ? 'bg-blue-600 text-white' 
                        : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                    }`}
                  >
                    <FileText className="w-4 h-4" />
                    LaTeX File
                  </button>
                  <button
                    onClick={() => setNewFileType('bib')}
                    className={`px-3 py-2 rounded flex items-center gap-2 text-sm transition-colors ${
                      newFileType === 'bib' 
                        ? 'bg-green-600 text-white' 
                        : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                    }`}
                  >
                    <Book className="w-4 h-4" />
                    Bibliography
                  </button>
                </div>
              </div>

              {/* Image Upload */}
              <div>
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="w-full px-3 py-2 rounded bg-purple-600 hover:bg-purple-700 text-white text-sm flex items-center justify-center gap-2 transition-colors"
                >
                  <Upload className="w-4 h-4" />
                  Upload Image(s)
                </button>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  multiple
                  onChange={handleImageUpload}
                  className="hidden"
                />
                <p className="text-xs text-gray-500 mt-1">PNG, JPG, PDF supported</p>
              </div>

              {newFileType !== 'image' && (
                <>
                  <div>
                    <label className="block text-sm text-gray-300 mb-2">File Name</label>
                    <input
                      type="text"
                      value={newFileName}
                      onChange={(e) => setNewFileName(e.target.value)}
                      onKeyPress={(e) => e.key === 'Enter' && handleAddFile()}
                      placeholder={newFileType === 'bib' ? 'references.bib' : 'chapter1.tex'}
                      className="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                      autoFocus
                    />
                  </div>

                  <button
                    onClick={handleAddFile}
                    disabled={!newFileName.trim()}
                    className="w-full px-4 py-2 rounded bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium transition-colors"
                  >
                    Add File
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Document Selector Dialog */}
      {showDocumentSelector && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-gray-800 rounded-lg border border-gray-700 p-4 w-full max-w-md">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-white">Select Document</h3>
              <button
                onClick={() => setShowDocumentSelector(false)}
                className="p-1 rounded hover:bg-gray-700 text-gray-400"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="space-y-2">
              {documents.map((doc) => (
                <button
                  key={doc.name}
                  onClick={() => {
                    setCurrentDocument(doc.name);
                    setShowDocumentSelector(false);
                  }}
                  className={`w-full px-3 py-2 rounded flex items-center gap-2 text-left transition-colors ${
                    currentDocument === doc.name
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                  }`}
                >
                  <FolderOpen className="w-4 h-4" />
                  {doc.name}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Image Preview Modal */}
      {imagePreview && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4" onClick={() => setImagePreview(null)}>
          <div className="bg-gray-800 rounded-lg border border-gray-700 p-4 max-w-4xl max-h-[90vh] overflow-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-white">{imagePreview.name}</h3>
              <button
                onClick={() => setImagePreview(null)}
                className="p-1 rounded hover:bg-gray-700 text-gray-400"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="flex justify-center">
              <img 
                src={`data:image/png;base64,${imagePreview.content}`}
                alt={imagePreview.name}
                className="max-w-full max-h-[70vh] object-contain rounded"
              />
            </div>
            <div className="mt-4 p-3 bg-gray-900 rounded">
              <p className="text-xs text-gray-400 mb-1">LaTeX code to include this image:</p>
              <code className="text-sm text-green-400 block">
                {`\\includegraphics[width=0.8\\textwidth]{${imagePreview.name}}`}
              </code>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
