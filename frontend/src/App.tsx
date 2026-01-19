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
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'

function App() {
  const [workflows, setWorkflows] = useState<string[]>([])
  const [selectedWorkflow, setSelectedWorkflow] = useState('')

  // Image mode
  const [imagePrompt, setImagePrompt] = useState(
    'A cute girl version of the reference toddler character, same pose, same yellow onesie, Pixar style, full body'
  )
  const [width, setWidth] = useState(1024)
  const [height, setHeight] = useState(1024)
  const [steps, setSteps] = useState(9);
  // Video mode
  const [videoPrompt, setVideoPrompt] = useState(
    'Cinematic scene: a man in black tuxedo sings opera in red-tiled bathroom, emotional performance, static camera'
  )
  const [fps, setFps] = useState(24)
  const [frameCount, setFrameCount] = useState(121)

  const [results, setResults] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [referenceFile, setReferenceFile] = useState<File | null>(null)
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const [shift, setShift] = useState(3.0);  // default 3.0
  const [activeTab, setActiveTab] = useState('image')

  // Load workflows
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
      formData.append('workflow_name', selectedWorkflow)

      // Common
      if (referenceFile) {
        formData.append('reference_image', referenceFile)
      }

      // Mode-specific
      if (activeTab === 'image') {
        formData.append('prompt', imagePrompt.trim())
        formData.append('width', String(width))
        formData.append('height', String(height))
      } else {
        // video
        formData.append('prompt', videoPrompt.trim())
        formData.append('width', '1280') // typical for LTX-2
        formData.append('height', '720')
        formData.append('fps', String(fps))
        formData.append('frame_count', String(frameCount))
      }

      formData.append('steps', String(steps));
      formData.append('shift', shift.toFixed(1));

      const res = await fetch('http://localhost:8000/generate', {
        method: 'POST',
        body: formData,
      })

      if (!res.ok) {
        const errText = await res.text()
        throw new Error(`Generation failed: ${res.status} - ${errText}`)
      }

      const data = await res.json()
      setResults(data.images || data.media || [])
    } catch (err: any) {
      setError(err.message || 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-white via-slate-50 to-indigo-50 p-6 md:p-8 text-slate-900">
      <div className="max-w-5xl mx-auto space-y-10">
        <div className="text-center">
          <h1 className="text-4xl md:text-5xl font-bold mb-2 text-slate-900">
            ComfyUI Runner
          </h1>
          <p className="text-slate-600">Generate images & videos locally</p>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="grid w-full grid-cols-2 mb-6">
            <TabsTrigger value="image">Image Generation</TabsTrigger>
            <TabsTrigger value="video">Video Generation</TabsTrigger>
          </TabsList>

          {/* IMAGE TAB */}
          <TabsContent value="image">
            <Card className="border-slate-200 shadow-sm">
              <CardHeader>
                <CardTitle>Image Settings</CardTitle>
                <CardDescription>Text-to-image generation</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6 pt-2">
                {/* Workflow */}
                <div className="space-y-2">
                  <label className="text-sm font-medium">Workflow</label>
                  <Select value={selectedWorkflow} onValueChange={setSelectedWorkflow}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select workflow..." />
                    </SelectTrigger>
                    <SelectContent>
                      {workflows.map(wf => (
                        <SelectItem key={wf} value={wf}>
                          {wf}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* Prompt */}
                <div className="space-y-2">
                  <label className="text-sm font-medium">Prompt</label>
                  <Textarea
                    value={imagePrompt}
                    onChange={e => setImagePrompt(e.target.value)}
                    placeholder="Describe your desired image..."
                    className="min-h-[140px]"
                  />
                </div>

                {/* Dimensions */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="text-sm font-medium">Width</label>
                    <input
                      type="number"
                      min={256}
                      step={64}
                      value={width}
                      onChange={e => setWidth(Number(e.target.value))}
                      className="w-full rounded-md border px-3 py-2"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-sm font-medium">Height</label>
                    <input
                      type="number"
                      min={256}
                      step={64}
                      value={height}
                      onChange={e => setHeight(Number(e.target.value))}
                      className="w-full rounded-md border px-3 py-2"
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Shift (Noise Schedule)</label>
                  <div className="flex items-center gap-4">
                    <input
                      type="range"
                      min={1.0}
                      max={7.0}
                      step={0.1}
                      value={shift}
                      onChange={(e) => setShift(Number(e.target.value))}
                      className="w-full"
                    />
                    <span className="text-sm font-medium w-12 text-center">{shift.toFixed(1)}</span>
                  </div>
                  <p className="text-xs text-slate-500">
                    {shift <= 3 ? 'Faster, more details early' : shift >= 5 ? 'Cleaner, better composition' : 'Balanced'}
                  </p>
                </div>

                <div className="space-y-1.5">
                  <label className="text-sm font-medium">Steps (4-20 recommended)</label>
                  <input
                    type="number"
                    min={4}
                    max={20}
                    step={1}
                    value={steps}
                    onChange={e => setSteps(Number(e.target.value))}
                    className="w-full rounded-md border px-3 py-2"
                  />
                  <p className="text-xs text-slate-500">Lower = faster, higher = more detail</p>
                </div>

                {/* Reference */}
                <div className="space-y-2">
                  <label className="text-sm font-medium">Reference Image (optional)</label>
                  <div className="flex items-center gap-3">
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept="image/*"
                      onChange={e => setReferenceFile(e.target.files?.[0] ?? null)}
                      className="block w-full text-sm text-slate-600 file:mr-4 file:rounded file:border-0 file:bg-slate-100 file:px-4 file:py-2 hover:file:bg-slate-200"
                    />
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={!referenceFile}
                      onClick={() => {
                        setReferenceFile(null)
                        if (fileInputRef.current) fileInputRef.current.value = ''
                      }}
                    >
                      Clear
                    </Button>
                  </div>
                  {referenceFile && (
                    <p className="text-xs text-slate-500">
                      Selected: {referenceFile.name}
                    </p>
                  )}
                </div>

                <Button
                  onClick={handleGenerate}
                  disabled={loading || !selectedWorkflow || !imagePrompt.trim()}
                  className="w-full h-12 text-lg bg-indigo-600 hover:bg-indigo-700"
                >
                  {loading ? 'Generating...' : 'Generate Image'}
                </Button>
              </CardContent>
            </Card>
          </TabsContent>

          {/* VIDEO TAB */}
          <TabsContent value="video">
            <Card className="border-slate-200 shadow-sm">
              <CardHeader>
                <CardTitle>Video Settings</CardTitle>
                <CardDescription>
                  Text-to-video (LTX-2 recommended: 1280×720, ~5 seconds)
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6 pt-2">
                {/* Workflow */}
                <div className="space-y-2">
                  <label className="text-sm font-medium">Workflow</label>
                  <Select value={selectedWorkflow} onValueChange={setSelectedWorkflow}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select video workflow..." />
                    </SelectTrigger>
                    <SelectContent>
                      {workflows.map(wf => (
                        <SelectItem key={wf} value={wf}>
                          {wf}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* Prompt */}
                <div className="space-y-2">
                  <label className="text-sm font-medium">Video Prompt</label>
                  <Textarea
                    value={videoPrompt}
                    onChange={e => setVideoPrompt(e.target.value)}
                    placeholder="Describe the scene, action, mood, camera..."
                    className="min-h-[160px]"
                  />
                </div>

                {/* Video params */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="text-sm font-medium">FPS</label>
                    <input
                      type="number"
                      min={12}
                      max={60}
                      value={fps}
                      onChange={e => setFps(Number(e.target.value))}
                      className="w-full rounded-md border px-3 py-2"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-sm font-medium">Frames</label>
                    <input
                      type="number"
                      min={16}
                      step={8}
                      value={frameCount}
                      onChange={e => setFrameCount(Number(e.target.value))}
                      className="w-full rounded-md border px-3 py-2"
                    />
                  </div>
                </div>

                {/* Reference (for future I2V support) */}
                <div className="space-y-2">
                  <label className="text-sm font-medium">Reference Image (optional)</label>
                  {/* same reference input as image tab */}
                  <div className="flex items-center gap-3">
                    <input
                      type="file"
                      accept="image/*"
                      onChange={e => setReferenceFile(e.target.files?.[0] ?? null)}
                      className="block w-full text-sm text-slate-600 file:mr-4 file:rounded file:border-0 file:bg-slate-100 file:px-4 file:py-2 hover:file:bg-slate-200"
                    />
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={!referenceFile}
                      onClick={() => {
                        setReferenceFile(null)
                        if (fileInputRef.current) fileInputRef.current.value = ''
                      }}
                    >
                      Clear
                    </Button>
                  </div>
                </div>

                <Button
                  onClick={handleGenerate}
                  disabled={loading || !selectedWorkflow || !videoPrompt.trim()}
                  className="w-full h-12 text-lg bg-violet-600 hover:bg-violet-700"
                >
                  {loading ? 'Generating Video...' : 'Generate Video'}
                </Button>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        {/* Results */}
        {results.length > 0 && (
          <Card className="border-slate-200 shadow-sm">
            <CardHeader>
              <CardTitle>
                {activeTab === 'video' ? 'Generated Video' : 'Generated Images'}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {results.map((url, i) => {
  const isVideo = url.toLowerCase().endsWith('.mp4') || 
                  url.toLowerCase().endsWith('.webm') || 
                  url.toLowerCase().endsWith('.gif');

  return (
    <div
      key={i}
      className="rounded-lg overflow-hidden border border-slate-200 bg-white shadow-sm"
    >
      {isVideo ? (
        <video
          controls
          loop
          autoPlay
          muted={false}           // ← try without muted first
          playsInline             // important for mobile & some browsers
          className="w-full h-auto"
          onError={(e) => {
            console.error("Video failed to load:", url, e);
            alert("Video load error - check console for details");
          }}
          onLoadedData={() => console.log("Video loaded successfully:", url)}
        >
          <source src={url} type="video/mp4" />  {/* explicit type helps */}
          Your browser does not support the video tag.
        </video>
      ) : (
        <img
          src={url}
          alt={`Generated ${i + 1}`}
          className="w-full h-auto"
          onError={() => console.error("Image failed:", url)}
        />
      )}
    </div>
  );
})}
              </div>
            </CardContent>
          </Card>
        )}

        {error && (
          <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 mt-6">
            {error}
          </div>
        )}
      </div>
    </div>
  )
}

export default App