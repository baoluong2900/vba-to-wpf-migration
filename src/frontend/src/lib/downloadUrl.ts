/** Download URL for a Layer 4 output, with each segment percent-encoded. */
export function layer4DownloadUrl(docKind: string, docType: string, filename: string): string {
  return ['/api/v1/layer4/download', docKind, docType, filename]
    .map((segment, i) => (i === 0 ? segment : encodeURIComponent(segment)))
    .join('/');
}

// The backend's own download_url (layer4/server.py::_download_url) is already percent-encoded:
// use it unchanged — encoding it again breaks non-ASCII file names.
