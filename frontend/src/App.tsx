import { useState, useEffect, useRef } from 'react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'

function App() {
  const [workflows, setWorkflows] = useState<string[]>([])
  const [selectedWorkflow, setSelectedWorkflow] = useState('')
  const [prompt, setPrompt] = useState(
    'A cute girl version of the reference toddler character, same pose, same yellow onesie, Pixar style, full body'
  )
  const [results, setResults] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [referenceFile, setReferenceFile] = useState<File | null>(null)
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const [width, setWidth] = useState(1024)
  const [height, setHeight] = useState(1024)

  // Load workflows from backend on mount
  useEffect(() => {
    fetch('http://localhost:8000/workflows')
      .then(res => {
        if (!res.ok) throw new Error('Failed to fetch workflows')
        return res.json()
      })
      .then(data => {
        const wfList = data.workflows || []
        setWorkflows(wfList)
        if (wfList.length > 0) setSelectedWorkflow(wfList[0])
      })
      .catch(err => setError(err.message))
  }, [])

  const handleGenerate = async () => {
    if (!selectedWorkflow) return

    setLoading(true)
    setError(null)
    setResults([])

    try {
      const formData = new FormData()
      formData.append("workflow_name", selectedWorkflow)
      formData.append("prompt", prompt.trim())
      formData.append("width", String(width))
      formData.append("height", String(height))

      if (referenceFile) {
        formData.append("reference_image", referenceFile)
      }

      const res = await fetch("http://localhost:8000/generate", {
        method: "POST",
        body: formData,
      })

      if (!res.ok) {
        const errText = await res.text()
        throw new Error(`Generation failed: ${res.status} - ${errText}`)
      }

      const data = await res.json()
      setResults(data.images || [])
    } catch (err: any) {
      setError(err.message || "Unknown error")
    } finally {
      setLoading(false)
    }
  }


  return (
    <div className="min-h-screen bg-gradient-to-br from-white via-slate-50 to-indigo-50 p-8 text-slate-900">
      <div className="max-w-4xl mx-auto space-y-10">
        <div className="text-center">
          <h1 className="text-4xl md:text-5xl font-bold mb-2 text-slate-900">NAS → ComfyUI Runner</h1>
          <p className="text-slate-500">Generate images with your local workflows</p>
        </div>

        <Card className="bg-white border-slate-200 shadow-sm">
          <CardHeader>
            <CardTitle>Configure Generation</CardTitle>
            <CardDescription>Select workflow and enter your prompt</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-2">
              <label className="text-sm font-medium">Workflow</label>
              <Select value={selectedWorkflow} onValueChange={setSelectedWorkflow}>
                <SelectTrigger className="bg-white border-slate-200 text-slate-900">
                  <SelectValue placeholder="Choose a workflow..." />
                </SelectTrigger>
                <SelectContent>
                  {workflows.map(wf => (
                    <SelectItem key={wf} value={wf}>{wf}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Prompt</label>
              <Textarea
                value={prompt}
                onChange={e => setPrompt(e.target.value)}
                placeholder="Describe your image..."
                className="min-h-[140px] bg-white border-slate-200 font-mono text-slate-900 placeholder:text-slate-400"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="text-sm font-medium">Width</label>
                <input
                  type="number"
                  min={256}
                  step={64}
                  value={width}
                  onChange={(e) => setWidth(Number(e.target.value))}
                  className="w-full rounded-md border border-slate-200 px-3 py-2"
                />
              </div>

              <div className="space-y-1">
                <label className="text-sm font-medium">Height</label>
                <input
                  type="number"
                  min={256}
                  step={64}
                  value={height}
                  onChange={(e) => setHeight(Number(e.target.value))}
                  className="w-full rounded-md border border-slate-200 px-3 py-2"
                />
              </div>
            </div>


            <div className="space-y-2">
              <label className="text-sm font-medium">Reference Image (optional)</label>

              <div className="flex items-center gap-3">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  onChange={(e) => setReferenceFile(e.target.files?.[0] ?? null)}
                  className="block w-full text-sm text-slate-700
                 file:mr-4 file:rounded-md file:border-0
                 file:bg-slate-100 file:px-4 file:py-2
                 file:text-sm file:font-medium file:text-slate-700
                 hover:file:bg-slate-200"
                />

                <Button
                  type="button"
                  variant="outline"
                  disabled={!referenceFile}
                  onClick={() => {
                    setReferenceFile(null)
                    if (fileInputRef.current) fileInputRef.current.value = ""
                  }}
                >
                  Clear
                </Button>
              </div>

              {referenceFile && (
                <p className="text-xs text-slate-500">
                  Selected: <span className="font-mono">{referenceFile.name}</span>
                </p>
              )}
            </div>


            <Button
              onClick={handleGenerate}
              disabled={loading || workflows.length === 0 || !prompt.trim()}
              className="w-full bg-indigo-600 hover:bg-indigo-700 h-12 text-lg text-white"
            >
              {loading ? 'Generating...' : 'Generate Image →'}
            </Button>

            {error && (
              <div className="p-4 bg-red-50 border border-red-200 rounded text-red-700">
                Error: {error}
              </div>
            )}
          </CardContent>
        </Card>

        {results.length > 0 && (
          <Card className="bg-white border-slate-200 shadow-sm">
            <CardHeader>
              <CardTitle>Results</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {results.map((url, i) => (
                  <div key={i} className="rounded-xl overflow-hidden border border-slate-200 bg-white shadow-sm">
                    <img src={url} alt={`Generated ${i + 1}`} className="w-full h-auto" />
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}

export default App