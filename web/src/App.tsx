import { useEffect, useState } from 'react'
import { correctSource, extractImage, extractText, getHealth, getReport, investigate } from './api'
import type { Draft, Report } from './types'

type Stage = 'input' | 'extracting' | 'review' | 'investigating' | 'result'
type ServiceState = 'checking' | 'ready' | 'nebius_missing' | 'tavily_missing' | 'both_missing' | 'unavailable'

const exampleReport: Report = {
  id: 'example',
  created_at: '2026-10-27T00:00:00Z',
  claim: 'The Transformer was proven better on every language task.',
  search_query: 'Attention Is All You Need machine translation 2017',
  status: 'candidate_source',
  message: 'The paper supports a narrower result than the illustrative claim.',
  candidates: [],
  selected_source: {
    title: 'Attention Is All You Need',
    url: 'https://arxiv.org/abs/1706.03762',
    snippet: 'Vaswani and colleagues, 2017',
  },
  comparison: {
    supporting_excerpt: 'Experiments on two machine translation tasks show these models to be superior in quality while being more parallelizable',
    study_tested: 'Two machine translation tasks, with an additional English parsing experiment described in the abstract.',
    study_found: 'The authors reported stronger quality and greater parallelizability on the translation tasks they tested.',
    wording_gap: 'The quoted evidence concerns specific translation tasks. It does not establish superiority on every language task.',
    uncertainties: ['This short excerpt does not establish how the architecture performs on unrelated tasks.'],
    excerpt_verified: true,
  },
  selection_reason: 'This is the original paper used for the worked example.',
  trace: [],
  corrections: [],
}

function SourceLink({ title, url }: { title: string; url: string }) {
  return <a href={url} target="_blank" rel="noopener noreferrer">{title}<span aria-hidden="true"> ↗</span></a>
}

function App() {
  const [mode, setMode] = useState<'text' | 'image'>('text')
  const [stage, setStage] = useState<Stage>('input')
  const [inputText, setInputText] = useState('')
  const [imageFile, setImageFile] = useState<File | null>(null)
  const [imagePreview, setImagePreview] = useState<string | null>(null)
  const [draft, setDraft] = useState<Draft | null>(null)
  const [report, setReport] = useState<Report | null>(null)
  const [error, setError] = useState('')
  const [serviceState, setServiceState] = useState<ServiceState>('checking')
  const [isExample, setIsExample] = useState(false)
  const [copied, setCopied] = useState(false)
  const [sourceUpdating, setSourceUpdating] = useState('')
  const [sourceUrl, setSourceUrl] = useState('')

  useEffect(() => {
    getHealth()
      .then(({ providers_configured }) => {
        const { nebius, tavily } = providers_configured
        setServiceState(nebius && tavily ? 'ready' : !nebius && !tavily ? 'both_missing' : !nebius ? 'nebius_missing' : 'tavily_missing')
      })
      .catch(() => setServiceState('unavailable'))
    const reportId = new URLSearchParams(window.location.search).get('report')
    if (reportId) {
      getReport(reportId)
        .then((saved) => { setIsExample(false); setReport(saved); setStage('result') })
        .catch(() => setError('That saved investigation could not be opened. Start a new one below.'))
    }
  }, [])

  useEffect(() => {
    if (!imageFile) { setImagePreview(null); return }
    const url = URL.createObjectURL(imageFile)
    setImagePreview(url)
    return () => URL.revokeObjectURL(url)
  }, [imageFile])

  async function handleExtract() {
    setError('')
    setStage('extracting')
    try {
      const result = mode === 'text' ? await extractText(inputText) : await extractImage(imageFile!)
      setDraft(result)
      setStage('review')
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Claim extraction failed.')
      setStage('input')
    }
  }

  async function handleInvestigate() {
    if (!draft) return
    setError('')
    setStage('investigating')
    try {
      const result = await investigate(draft.claim, draft.search_query)
      setIsExample(false)
      setReport(result)
      window.history.replaceState({}, '', `?report=${encodeURIComponent(result.id)}`)
      setStage('result')
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'The investigation could not finish.')
      setStage('review')
    }
  }

  async function handleCorrection(url: string) {
    if (!report) return
    setSourceUpdating(url)
    setError('')
    try {
      setReport(await correctSource(report.id, url))
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'The source could not be checked.')
    } finally {
      setSourceUpdating('')
    }
  }

  function startOver() {
    setStage('input')
    setDraft(null)
    setReport(null)
    setError('')
    setCopied(false)
    setSourceUrl('')
    setIsExample(false)
    window.history.replaceState({}, '', window.location.pathname)
  }

  function showExample() {
    setError('')
    setIsExample(true)
    setReport(exampleReport)
    setStage('result')
    window.history.replaceState({}, '', window.location.pathname)
    document.getElementById('workbench')?.scrollIntoView({ block: 'start' })
  }

  async function shareReport() {
    if (!report) return
    try {
      await navigator.clipboard.writeText(window.location.href)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2500)
    } catch {
      setError('Copying failed. You can copy the URL from your browser instead.')
    }
  }

  return (
    <div className="site-shell">
      <header className="topbar">
        <a className="brand" href="/" onClick={(event) => { event.preventDefault(); startOver() }} aria-label="StudyLens home">
          <span className="brand-mark" aria-hidden="true"><span /></span>
          <span>StudyLens</span>
        </a>
        <div className="topbar-right">
          <button className="topbar-example" onClick={showExample}>View an example</button>
          <span className={`service-pill ${serviceState}`}>{serviceState === 'ready' ? 'Live research ready' : serviceState === 'checking' ? 'Checking research service' : serviceState === 'nebius_missing' ? 'Model access pending' : serviceState === 'tavily_missing' ? 'Search access pending' : serviceState === 'both_missing' ? 'Research service pending' : 'Research service offline'}</span>
        </div>
      </header>

      <main>
        <section className="intro" aria-labelledby="intro-title">
          <div className="intro-copy">
            <div className="intro-rule"><span className="intro-rule-dot" /><span>Research, in context</span></div>
            <h1 id="intro-title">Find the paper behind the claim.</h1>
            <p className="intro-description">Paste a research claim or upload a screenshot. StudyLens traces it to an original source and shows what the evidence actually covers.</p>
            <button className="intro-example" onClick={showExample}>Explore a worked example <span aria-hidden="true">↗</span></button>
          </div>
          <div className="specimen" aria-hidden="true">
            <div className="specimen-top"><span>Illustrative claim</span><p>“Better on <mark>every language task.</mark>”</p></div>
            <div className="specimen-connector"><span className="connector-node" /><span className="connector-line" /><span className="connector-node last" /></div>
            <div className="specimen-bottom"><span>Original paper · 2017</span><p>“<mark>two machine translation tasks</mark>”</p><small>The scope of the evidence is narrower.</small></div>
          </div>
        </section>

        {serviceState !== 'ready' && serviceState !== 'checking' && <div className="setup-notice" role="status"><span className="notice-mark" aria-hidden="true">i</span><span>{serviceState === 'unavailable' ? 'The research service is offline. The worked example is still available.' : serviceState === 'nebius_missing' ? 'Live investigations are waiting for Nebius model access. You can explore the worked example now.' : serviceState === 'tavily_missing' ? 'Live investigations are waiting for source search access. You can explore the worked example now.' : 'Live investigations are being connected. You can explore the worked example now.'}</span></div>}
        {error && <div className="error-notice" role="alert">{error}</div>}

        <div className="workbench" id="workbench">
          <section className="claim-panel" aria-labelledby="claim-heading">
            <div className="panel-heading"><span className="panel-icon">1</span><div><p className="panel-label">Start with the wording</p><h2 id="claim-heading">The claim</h2></div></div>
            {stage === 'result' && report ? (
              <>
                <blockquote className="confirmed-claim">{report.claim}</blockquote>
                <button className="text-button" onClick={startOver}>Investigate another claim</button>
              </>
            ) : stage === 'review' || (stage === 'investigating' && draft) ? (
              <div className="draft-fields">
                <p className="field-help">Check the extracted wording before searching. You can edit it.</p>
                <label htmlFor="claim-edit">Research claim</label>
                <textarea id="claim-edit" rows={5} value={draft?.claim || ''} onChange={(event) => setDraft((current) => current ? { ...current, claim: event.target.value } : current)} disabled={stage === 'investigating'} />
                <label htmlFor="search-edit">Search phrase</label>
                <input id="search-edit" value={draft?.search_query || ''} onChange={(event) => setDraft((current) => current ? { ...current, search_query: event.target.value } : current)} disabled={stage === 'investigating'} />
                <div className="action-row"><button className="primary-button" onClick={handleInvestigate} disabled={stage === 'investigating' || (draft?.claim.length || 0) < 15 || (draft?.search_query.length || 0) < 5}>{stage === 'investigating' ? 'Tracing the source…' : 'Trace this claim'}</button><button className="secondary-button" onClick={startOver} disabled={stage === 'investigating'}>Start over</button></div>
              </div>
            ) : (
              <div className="entry-fields">
                <div className="mode-switch" role="group" aria-label="Input type"><button className={mode === 'text' ? 'selected' : ''} aria-pressed={mode === 'text'} onClick={() => setMode('text')}>Paste text</button><button className={mode === 'image' ? 'selected' : ''} aria-pressed={mode === 'image'} onClick={() => setMode('image')}>Upload screenshot</button></div>
                {mode === 'text' ? <><label htmlFor="claim-input">Claim or passage</label><textarea id="claim-input" rows={7} placeholder="Paste a claim about a scientific or technical study…" value={inputText} onChange={(event) => setInputText(event.target.value)} /><p className="field-help">Include the original wording, especially numbers or qualifiers.</p></> : <><label htmlFor="screenshot-input">Screenshot</label><input id="screenshot-input" className="file-input" type="file" accept="image/png,image/jpeg,image/webp" onChange={(event) => setImageFile(event.target.files?.[0] || null)} /><p className="field-help">PNG, JPEG, or WebP, up to 5 MB. Use a public post without personal information.</p>{imagePreview && <img className="image-preview" src={imagePreview} alt="Screenshot to investigate" />}</>}
                <button className="primary-button" onClick={handleExtract} disabled={stage === 'extracting' || (mode === 'text' ? inputText.trim().length < 20 : !imageFile)}>{stage === 'extracting' ? 'Reading the claim…' : 'Find the research claim'}</button>
              </div>
            )}
          </section>

          <section className="evidence-panel" aria-labelledby="evidence-heading">
            <div className="panel-heading"><span className="panel-icon source-icon">2</span><div><p className="panel-label">Follow it to the source</p><h2 id="evidence-heading">The evidence</h2></div></div>
            {stage === 'result' && report ? (
              <div className="report-body">
                {isExample && <div className="example-ribbon"><span>Worked example</span><p>Prepared from a published abstract to show the interface. No live model call was used for this example.</p></div>}
                <div className={`finding-status ${report.status}`}><span className="status-symbol" aria-hidden="true">{report.status === 'candidate_source' ? '↗' : '?'}</span><div><strong>{isExample ? 'Published source in this example' : report.status === 'candidate_source' ? 'Candidate source found' : 'Source not confirmed'}</strong><p>{report.message}</p></div></div>
                {report.selected_source && report.comparison && <>
                  <div className="source-title"><span>{isExample ? 'Published paper' : 'Original research candidate'}</span><SourceLink title={report.selected_source.title} url={report.selected_source.url} /></div>
                  {report.selection_reason && <p className="selection-reason">Why this source: {report.selection_reason}</p>}
                  <div className="source-quote"><span>Passage found in the source</span><blockquote>“{report.comparison.supporting_excerpt}”</blockquote></div>
                  <div className="comparison-grid"><div><h3>What was tested</h3><p>{report.comparison.study_tested || 'Not stated in the accessible text.'}</p></div><div><h3>What the study found</h3><p>{report.comparison.study_found || 'Not stated in the accessible text.'}</p></div><div className="wording-gap"><h3>Where the wording changes</h3><p>{report.comparison.wording_gap || 'No clear wording difference identified.'}</p></div></div>
                  {report.comparison.uncertainties.length > 0 && <div className="uncertainties"><h3>Still uncertain</h3><ul>{report.comparison.uncertainties.map((item, index) => <li key={index}>{item}</li>)}</ul></div>}
                </>}
                {!isExample && <>
                  {report.candidates.length > 0 && <details className="candidate-list"><summary>Inspect other research pages ({report.candidates.length})</summary><ul>{report.candidates.map((source) => <li key={source.url}><SourceLink title={source.title || source.url} url={source.url} /><p>{source.snippet}</p><button className="text-button" disabled={Boolean(sourceUpdating) || source.url === report.selected_source?.url} onClick={() => handleCorrection(source.url)}>{sourceUpdating === source.url ? 'Checking this source…' : source.url === report.selected_source?.url ? 'Current source' : 'Check this source'}</button></li>)}</ul></details>}
                  <div className="source-correction"><label htmlFor="source-url">Know the original study?</label><p className="field-help">Add its public research URL. StudyLens will check the page text before showing it as a source.</p><div className="source-correction-row"><input id="source-url" type="url" placeholder="https://arxiv.org/abs/…" value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} /><button className="secondary-button" disabled={Boolean(sourceUpdating) || !sourceUrl.trim()} onClick={() => handleCorrection(sourceUrl.trim())}>{sourceUpdating === sourceUrl.trim() ? 'Checking…' : 'Check source'}</button></div></div>
                  {report.corrections.length > 0 && <details className="trace-list"><summary>Source corrections ({report.corrections.length})</summary><ol>{report.corrections.map((item, index) => <li key={index}>Checked <a href={item.new_url} target="_blank" rel="noopener noreferrer">{item.new_url}</a>{item.previous_url ? ` after ${item.previous_url}` : ''}</li>)}</ol></details>}
                </>}
                <div className="report-actions">{isExample ? <button className="secondary-button" onClick={startOver}>Try your own claim</button> : <button className="secondary-button" onClick={shareReport}>{copied ? 'Link copied' : 'Copy report link'}</button>}<span>{isExample ? 'Illustrative report' : `Saved ${new Date(report.created_at).toLocaleDateString()}`}</span></div>
                {!isExample && <details className="trace-list"><summary>How this investigation was made</summary><ol>{report.trace.map((step, index) => <li key={index}>{step}</li>)}</ol><p>Model output can be mistaken. Check the original source before sharing a conclusion.</p></details>}
              </div>
            ) : (
              <div className="empty-evidence">
                <div className="empty-graphic" aria-hidden="true"><span className="graphic-claim" /><span className="graphic-path" /><span className="graphic-source" /></div>
                <h3>{stage === 'investigating' ? 'Checking the original text' : stage === 'extracting' ? 'Reading the claim' : stage === 'review' ? 'Ready to trace' : 'A clear path back to the paper'}</h3>
                <p>{stage === 'investigating' ? 'StudyLens is searching research sources and checking the source passage.' : stage === 'extracting' ? 'Confirm the extracted wording before StudyLens searches for a paper.' : stage === 'review' ? 'Confirm the wording, then trace it to its source.' : 'See the source, a passage you can inspect, and where the public wording went beyond it.'}</p>
                {stage === 'input' && <button className="empty-example" onClick={showExample}>See a worked example <span aria-hidden="true">↗</span></button>}
              </div>
            )}
          </section>
        </div>
      </main>

      <footer className="footer"><span>StudyLens · Follow the evidence to its source.</span><span>An evidence trail, never a verdict.</span></footer>
    </div>
  )
}

export default App
