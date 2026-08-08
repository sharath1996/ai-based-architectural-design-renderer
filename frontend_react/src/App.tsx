import { useEffect, useMemo, useState } from 'react'
import './App.css'

type PromptPackStatus = {
  active_prompt_pack: string
  available_prompt_packs: string[]
}

type SpecExtractResponse = {
  spec: Record<string, string>
  bullet_points: string[]
}

type GenerateResponse = {
  images_base64: string[]
  count: number
}

type SpecRow = {
  key: string
  value: string
}

type ReferenceEntry = {
  id: string
  name: string
  mime: string
  file: File
  url: string
}

type ApiState = {
  loading: boolean
  error: string
}

const DEFAULT_BACKEND_URL = 'http://localhost:8000'
const REQUIRED_SPEC_HINT =
  'Select a style pack, choose a base anchor image, add support references if needed, then extract specs.'

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init)
  const payload = (await response.json().catch(() => null)) as T | null

  if (!response.ok) {
    const message =
      payload && typeof payload === 'object' && 'detail' in payload
        ? String((payload as { detail?: unknown }).detail ?? 'Request failed')
        : 'Request failed'
    throw new Error(message)
  }

  if (!payload) {
    throw new Error('Empty response from server')
  }

  return payload
}

function createEntry(file: File): ReferenceEntry {
  return {
    id: `${file.name}-${file.size}-${file.lastModified}`,
    name: file.name,
    mime: file.type || 'image/png',
    file,
    url: URL.createObjectURL(file),
  }
}

function emptyRow(): SpecRow {
  return { key: '', value: '' }
}

function App() {
  const [backendUrl, setBackendUrl] = useState(DEFAULT_BACKEND_URL)
  const [styleState, setStyleState] = useState<ApiState>({ loading: false, error: '' })
  const [packs, setPacks] = useState<PromptPackStatus>({
    active_prompt_pack: '',
    available_prompt_packs: [],
  })
  const [selectedPack, setSelectedPack] = useState('')
  const [baseImage, setBaseImage] = useState<ReferenceEntry | null>(null)
  const [supportImages, setSupportImages] = useState<ReferenceEntry[]>([])
  const [supportPrompts, setSupportPrompts] = useState<Record<string, string>>({})
  const [specRows, setSpecRows] = useState<SpecRow[]>([emptyRow()])
  const [specState, setSpecState] = useState<ApiState>({ loading: false, error: '' })
  const [specBullets, setSpecBullets] = useState<string[]>([])
  const [globalPrompt, setGlobalPrompt] = useState('')
  const [generateState, setGenerateState] = useState<ApiState>({ loading: false, error: '' })
  const [generatedImage, setGeneratedImage] = useState<string>('')
  const [backendHealthy, setBackendHealthy] = useState<boolean | null>(null)
  const [healthChecked, setHealthChecked] = useState(false)

  useEffect(() => {
    return () => {
      if (baseImage) URL.revokeObjectURL(baseImage.url)
      supportImages.forEach((entry) => URL.revokeObjectURL(entry.url))
    }
  }, [baseImage, supportImages])

  useEffect(() => {
    let alive = true

    async function loadPromptPacks() {
      setStyleState({ loading: true, error: '' })
      try {
        const data = await fetchJson<PromptPackStatus>(`${backendUrl}/prompt-packs`)
        if (!alive) return
        setPacks(data)
        setSelectedPack(data.active_prompt_pack || data.available_prompt_packs[0] || '')
        setStyleState({ loading: false, error: '' })
      } catch (error) {
        if (!alive) return
        setStyleState({ loading: false, error: error instanceof Error ? error.message : 'Failed to load styles' })
      }
    }

    loadPromptPacks()

    return () => {
      alive = false
    }
  }, [backendUrl])

  useEffect(() => {
    let alive = true

    async function checkHealth() {
      try {
        const response = await fetch(`${backendUrl}/health`)
        if (!alive) return
        setBackendHealthy(response.ok)
      } catch {
        if (!alive) return
        setBackendHealthy(false)
      }

      if (alive) {
        setHealthChecked(true)
      }
    }

    checkHealth()

    return () => {
      alive = false
    }
  }, [backendUrl])

  const supportPreviewRows = useMemo(
    () =>
      supportImages.map((entry, index) => ({
        index: index + 1,
        name: entry.name,
        prompt: supportPrompts[entry.id] || '',
      })),
    [supportImages, supportPrompts],
  )

  const activeStyleLabel = packs.active_prompt_pack || 'not selected'

  function updateRow(index: number, field: keyof SpecRow, value: string) {
    setSpecRows((rows) => rows.map((row, rowIndex) => (rowIndex === index ? { ...row, [field]: value } : row)))
  }

  function addRow() {
    setSpecRows((rows) => [...rows, emptyRow()])
  }

  function removeRow(index: number) {
    setSpecRows((rows) => rows.filter((_, rowIndex) => rowIndex !== index))
  }

  function syncRowsFromSpec(spec: Record<string, string>) {
    const nextRows = Object.entries(spec)
      .filter(([key]) => key !== 'error')
      .map(([key, value]) => ({ key, value }))
    setSpecRows(nextRows.length ? nextRows : [emptyRow()])
  }

  function specToObject() {
    return specRows.reduce<Record<string, string>>((acc, row) => {
      const key = row.key.trim()
      if (key) acc[key] = row.value.trim()
      return acc
    }, {})
  }

  function handleBaseUpload(fileList: FileList | null) {
    if (!fileList?.[0]) {
      if (baseImage) URL.revokeObjectURL(baseImage.url)
      setBaseImage(null)
      return
    }

    if (baseImage) URL.revokeObjectURL(baseImage.url)
    setBaseImage(createEntry(fileList[0]))
  }

  function handleSupportUpload(fileList: FileList | null) {
    supportImages.forEach((entry) => URL.revokeObjectURL(entry.url))
    const nextImages = fileList ? Array.from(fileList).map(createEntry) : []
    setSupportImages(nextImages)
    setSupportPrompts((existing) => {
      const next: Record<string, string> = {}
      nextImages.forEach((entry) => {
        next[entry.id] = existing[entry.id] || ''
      })
      return next
    })
  }

  async function applyPromptPack() {
    if (!selectedPack) return
    setStyleState({ loading: true, error: '' })
    try {
      const data = await fetchJson<PromptPackStatus>(`${backendUrl}/prompt-packs/select`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt_pack: selectedPack }),
      })
      setPacks(data)
      setStyleState({ loading: false, error: '' })
    } catch (error) {
      setStyleState({ loading: false, error: error instanceof Error ? error.message : 'Failed to set style' })
    }
  }

  async function refreshPromptPacks() {
    setStyleState({ loading: true, error: '' })
    try {
      const data = await fetchJson<PromptPackStatus>(`${backendUrl}/prompt-packs`)
      setPacks(data)
      setSelectedPack(data.active_prompt_pack || data.available_prompt_packs[0] || '')
      setStyleState({ loading: false, error: '' })
    } catch (error) {
      setStyleState({ loading: false, error: error instanceof Error ? error.message : 'Failed to refresh styles' })
    }
  }

  async function extractSpecs() {
    if (!baseImage) {
      setSpecState({ loading: false, error: 'Upload a base anchor image first.' })
      return
    }

    setSpecState({ loading: true, error: '' })
    try {
      const formData = new FormData()
      formData.append('files', baseImage.file, baseImage.name)
      supportImages.forEach((entry) => {
        formData.append('files', entry.file, entry.name)
      })

      const data = await fetchJson<SpecExtractResponse>(`${backendUrl}/spec/extract`, {
        method: 'POST',
        body: formData,
      })

      const extractedSpec = data.spec || {}
      syncRowsFromSpec(extractedSpec)
      setSpecBullets(data.bullet_points || [])
      if (extractedSpec.error) {
        setSpecRows([emptyRow()])
        setSpecState({ loading: false, error: extractedSpec.error })
      } else {
        setSpecState({ loading: false, error: '' })
      }
    } catch (error) {
      setSpecState({ loading: false, error: error instanceof Error ? error.message : 'Failed to extract specs' })
    }
  }

  async function generateImage() {
    if (!baseImage) {
      setGenerateState({ loading: false, error: 'Upload a base anchor image first.' })
      return
    }

    if (specState.error) {
      setGenerateState({ loading: false, error: specState.error })
      return
    }

    const specs = specToObject()
    if (Object.keys(specs).length === 0) {
      setGenerateState({ loading: false, error: 'Extract or enter specifications before generating.' })
      return
    }

    const supportPromptsJson = JSON.stringify(supportPreviewRows.map((row) => row.prompt))
    const formData = new FormData()
    formData.append('files', baseImage.file, baseImage.name)
    supportImages.forEach((entry) => {
      formData.append('files', entry.file, entry.name)
    })
    formData.append('prompt', globalPrompt)
    formData.append('support_prompts_json', supportPromptsJson)
    formData.append('spec_json', JSON.stringify(specs))

    setGenerateState({ loading: true, error: '' })
    try {
      const data = await fetchJson<GenerateResponse>(`${backendUrl}/generate/references`, {
        method: 'POST',
        body: formData,
      })
      setGeneratedImage(data.images_base64[0] || '')
      setGenerateState({ loading: false, error: data.images_base64[0] ? '' : 'No image was returned.' })
    } catch (error) {
      setGenerateState({ loading: false, error: error instanceof Error ? error.message : 'Failed to generate image' })
    }
  }

  const canGenerate = Boolean(baseImage) && Object.keys(specToObject()).length > 0 && !generateState.loading

  return (
    <div className="studio-shell">
      <div className="studio-background" />
      <div className="studio-grid" />

      <main className="studio-app">
        <section className="hero-card">
          <div className="hero-copy">
            <p className="eyebrow">AI Photo Studio</p>
            <h1>Minimal UI, premium output.</h1>
            <p className="hero-text">
              One base anchor image, multiple support references, a prompt pack selector, and a single polished final render.
            </p>
          </div>
          <div className="hero-meta">
            <div className={`status-chip ${backendHealthy ? 'good' : healthChecked ? 'bad' : 'neutral'}`}>
              <span className="status-dot" />
              {backendHealthy ? 'Backend online' : healthChecked ? 'Backend offline' : 'Checking backend...'}
            </div>
            <div className="style-chip">
              Active style: <strong>{activeStyleLabel}</strong>
            </div>
          </div>
        </section>

        <section className="toolbar-card card">
          <div className="toolbar-header">
            <div>
              <h2>Studio Settings</h2>
              <p>Choose the style pack that drives extraction and generation.</p>
            </div>
            <label className="backend-field">
              Backend URL
              <input value={backendUrl} onChange={(event) => setBackendUrl(event.target.value)} />
            </label>
          </div>

          <div className="toolbar-actions">
            <label className="select-field">
              Prompt pack
              <select value={selectedPack} onChange={(event) => setSelectedPack(event.target.value)}>
                {packs.available_prompt_packs.map((pack) => (
                  <option key={pack} value={pack}>
                    {pack}
                  </option>
                ))}
              </select>
            </label>
            <button className="primary-button" onClick={applyPromptPack} disabled={!selectedPack || styleState.loading}>
              Apply Style
            </button>
            <button className="ghost-button" onClick={refreshPromptPacks} disabled={styleState.loading}>
              Refresh
            </button>
          </div>

          {styleState.error ? <p className="error-line">{styleState.error}</p> : null}
        </section>

        <section className="content-grid">
          <div className="left-column">
            <section className="card">
              <div className="section-header">
                <div>
                  <h2>1. Base Anchor Image</h2>
                  <p>Main composition reference for the output.</p>
                </div>
              </div>

              <label className="upload-box base-upload">
                <input type="file" accept="image/*" onChange={(event) => handleBaseUpload(event.target.files)} />
                {baseImage ? (
                  <div className="preview-panel">
                    <img src={baseImage.url} alt={baseImage.name} />
                    <div>
                      <strong>{baseImage.name}</strong>
                      <span>Base anchor image</span>
                    </div>
                  </div>
                ) : (
                  <div className="upload-placeholder">
                    <span>Drop or choose one image</span>
                    <p>This image anchors the final composition.</p>
                  </div>
                )}
              </label>
            </section>

            <section className="card">
              <div className="section-header">
                <div>
                  <h2>2. Support References</h2>
                  <p>Upload multiple support references with a prompt for each one.</p>
                </div>
              </div>

              <label className="upload-box support-upload">
                <input type="file" accept="image/*" multiple onChange={(event) => handleSupportUpload(event.target.files)} />
                <div className="upload-placeholder">
                  <span>Drop or choose support images</span>
                  <p>These guide mood, material, lighting, and styling details.</p>
                </div>
              </label>

              {supportImages.length ? (
                <div className="support-list">
                  {supportImages.map((entry, index) => (
                    <article key={entry.id} className="support-item">
                      <img src={entry.url} alt={entry.name} />
                      <div className="support-copy">
                        <div className="support-head">
                          <strong>Support {index + 1}</strong>
                          <span>{entry.name}</span>
                        </div>
                        <label>
                          Support prompt
                          <textarea
                            value={supportPrompts[entry.id] || ''}
                            onChange={(event) =>
                              setSupportPrompts((current) => ({
                                ...current,
                                [entry.id]: event.target.value,
                              }))
                            }
                            placeholder="Describe what this support reference should influence."
                            rows={3}
                          />
                        </label>
                      </div>
                    </article>
                  ))}
                </div>
              ) : null}
            </section>

            <section className="card">
              <div className="section-header">
                <div>
                  <h2>Support Mapping Preview</h2>
                  <p>Verify image-to-prompt alignment before extraction and generation.</p>
                </div>
              </div>

              <div className="preview-table">
                <div className="preview-table-head">
                  <span>#</span>
                  <span>Reference</span>
                  <span>Prompt</span>
                </div>
                {supportPreviewRows.length ? (
                  supportPreviewRows.map((row) => (
                    <div className="preview-table-row" key={row.name}>
                      <span>{row.index}</span>
                      <span>{row.name}</span>
                      <span>{row.prompt || 'No prompt yet'}</span>
                    </div>
                  ))
                ) : (
                  <div className="preview-empty">No support references added yet.</div>
                )}
              </div>
            </section>
          </div>

          <div className="right-column">
            <section className="card">
              <div className="section-header compact">
                <div>
                  <h2>3. Extracted Specs</h2>
                  <p>{REQUIRED_SPEC_HINT}</p>
                </div>
                <button className="primary-button" onClick={extractSpecs} disabled={specState.loading || !baseImage}>
                  {specState.loading ? 'Extracting...' : 'Extract Specs'}
                </button>
              </div>

              {specState.error ? <p className="error-line">{specState.error}</p> : null}
              {specBullets.length ? (
                <ul className="bullet-list">
                  {specBullets.map((bullet) => (
                    <li key={bullet}>{bullet}</li>
                  ))}
                </ul>
              ) : null}

              <div className="spec-editor">
                <div className="spec-grid-head">
                  <span>Key</span>
                  <span>Value</span>
                  <span />
                </div>
                {specRows.map((row, index) => (
                  <div className="spec-grid-row" key={`${index}-${row.key}`}>
                    <input
                      value={row.key}
                      onChange={(event) => updateRow(index, 'key', event.target.value)}
                      placeholder="spec_key"
                    />
                    <input
                      value={row.value}
                      onChange={(event) => updateRow(index, 'value', event.target.value)}
                      placeholder="Value"
                    />
                    <button className="icon-button" onClick={() => removeRow(index)} aria-label="Remove row">
                      ×
                    </button>
                  </div>
                ))}
                <button className="ghost-button block-button" onClick={addRow}>
                  Add Row
                </button>
              </div>
            </section>

            <section className="card">
              <div className="section-header compact">
                <div>
                  <h2>4. Prompt</h2>
                  <p>Give the model a final creative direction.</p>
                </div>
              </div>

              <textarea
                className="global-prompt"
                rows={5}
                value={globalPrompt}
                onChange={(event) => setGlobalPrompt(event.target.value)}
                placeholder="Describe the final atmosphere, mood, color language, and finish."
              />
            </section>

            <section className="card generate-card">
              <div>
                <h2>5. Generate Final Image</h2>
                <p>The final output combines the base anchor, support signals, specs, and prompt pack.</p>
              </div>
              <button className="primary-button generate-button" onClick={generateImage} disabled={!canGenerate}>
                {generateState.loading ? 'Generating...' : 'Generate Final Image'}
              </button>
              {generateState.error ? <p className="error-line">{generateState.error}</p> : null}
            </section>

            <section className="card output-card">
              <div className="section-header compact">
                <div>
                  <h2>6. Final Output</h2>
                  <p>One premium render appears here.</p>
                </div>
              </div>

              {generatedImage ? (
                <div className="output-panel">
                  <img src={`data:image/png;base64,${generatedImage}`} alt="Generated final output" />
                  <a className="download-button" href={`data:image/png;base64,${generatedImage}`} download="generated_final_output.png">
                    Download Final Image
                  </a>
                </div>
              ) : (
                <div className="output-empty">Your final generated image will appear here.</div>
              )}
            </section>
          </div>
        </section>
      </main>
    </div>
  )
}

export default App
