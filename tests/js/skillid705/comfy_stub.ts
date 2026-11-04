// In-memory user files: every write and upload is recorded so tests can prove an import wrote nothing.
export const files: Record<string, string> = {}
export const writes: string[] = []
export const listUserFiles = async (dir: string, _deep?: boolean) => Object.keys(files).filter((p) => p.startsWith(dir + '/')).map((p) => p.slice(dir.length + 1))
export const readUserText = async (p: string) => (p in files ? files[p] : null)
export const writeUserText = async (p: string, s: string) => { writes.push(p); files[p] = s }
export const deleteUserFile = async (p: string) => { writes.push(`rm:${p}`); delete files[p] }
export const uploadImage = async (_b: unknown, name: string) => { writes.push(`upload:${name}`); return { filename: name, subfolder: '', type: 'input' } }
export const viewUrl = (r: { filename: string }) => `/view?filename=${r.filename}`
