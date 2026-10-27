import { useEffect, useState } from 'react'
import { correctSource, extractImage, extractText, getHealth, getReport, investigate } from './api'
import type { Draft, Report } from './types'

type Stage = 'input' | 'extracting' | 'review' | 'investigating' | 'result'

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
  const [serviceState, setServiceState] = useState<'checking' | 'ready' | 'unconfigured' | 'unavailable'>('checking')
  const [copied, setCopied] = useState(false)
  const [sourceUpdating, setSourceUpdating] = useState('')
  const [sourceUrl, setSourceUrl] = useState('')

  useEffect(() => {
    getHealth()
      .then(({ providers_configured }) => setServiceState(providers_configured.nebius && providers_configured.tavily ? 'ready' : 'unconfigured'))
      .catch(() => setServiceState('unavailable'))
    const reportId = new URLSearchParams(window.location.search).get('report')
    if (reportId) {
      getReport(reportId)
        .then((saved) => { setReport(saved); setStage('result') })
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
    window.history.replaceState({}, '', window.location.pathname)
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
          <span className="topbar-note">A clearer path to the original evidence</span>
          <span className={`service-pill ${serviceState}`}>{serviceState === 'ready' ? 'Live research' : serviceState === 'checking' ? 'Checking services' : serviceState === 'unconfigured' ? 'Services need keys' : 'API unavailable'}</span>
        </div>
      </header>

      <main>
        <section className="intro" aria-labelledby="intro-title">
          <div className="intro-copy">
            <p className="intro-kicker">Follow the evidence</p>
            <h1 id="intro-title">What did the study <em>actually</em> say?</h1>
            <p className="intro-description">Bring a claim from a post, article, or screenshot. Trace it to the research behind it, and see where the wording changed.</p>
          </div>
          <div className="intro-figure" aria-hidden="true">
            <div className="figure-claim">“A new study proves…”</div>
            <span className="figure-connector" />
            <div className="figure-source"><span className="figure-line long" /><span className="figure-line" /><span className="figure-line short" /></div>
            <div className="figure-caption">Claim → source → context</div>
          </div>
        </section>

        {serviceState === 'unconfigured' && <div className="setup-notice" role="status">The interface is ready. Live investigations begin after Nebius and Tavily keys are added to the API environment.</div>}
        {serviceState === 'unavailable' && <div className="setup-notice" role="status">The research service is offline. Start the API, then refresh this page.</div>}
        {error && <div className="error-notice" role="alert">{error}</div>}

        <div className="workbench">
          <section className="claim-panel" aria-labelledby="claim-heading">
            <div className="panel-heading"><span className="panel-icon">A</span><div><p className="panel-label">Start here</p><h2 id="claim-heading">The claim</h2></div></div>
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
            <div className="panel-heading"><span className="panel-icon source-icon">B</span><div><p className="panel-label">Follow through</p><h2 id="evidence-heading">The evidence</h2></div></div>
            {stage === 'result' && report ? (
              <div className="report-body">
                <div className={`finding-status ${report.status}`}><span className="status-symbol" aria-hidden="true">{report.status === 'candidate_source' ? '↗' : '?'}</span><div><strong>{report.status === 'candidate_source' ? 'Candidate source found' : 'Source not confirmed'}</strong><p>{report.message}</p></div></div>
                {report.selected_source && report.comparison && <>
                  <div className="source-title"><span>Original research candidate</span><SourceLink title={report.selected_source.title} url={report.selected_source.url} /></div>
                  {report.selection_reason && <p className="selection-reason">Why this source: {report.selection_reason}</p>}
                  <div className="source-quote"><span>Passage found in the source</span><blockquote>“{report.comparison.supporting_excerpt}”</blockquote></div>
                  <div className="comparison-grid"><div><h3>What was tested</h3><p>{report.comparison.study_tested || 'Not stated in the accessible text.'}</p></div><div><h3>What the study found</h3><p>{report.comparison.study_found || 'Not stated in the accessible text.'}</p></div><div className="wording-gap"><h3>Where the wording changes</h3><p>{report.comparison.wording_gap || 'No clear wording difference identified.'}</p></div></div>
                  {report.comparison.uncertainties.length > 0 && <div className="uncertainties"><h3>Still uncertain</h3><ul>{report.comparison.uncertainties.map((item, index) => <li key={index}>{item}</li>)}</ul></div>}
                </>}
                {report.candidates.length > 0 && <details className="candidate-list"><summary>Inspect other research pages ({report.candidates.length})</summary><ul>{report.candidates.map((source) => <li key={source.url}><SourceLink title={source.title || source.url} url={source.url} /><p>{source.snippet}</p><button className="text-button" disabled={Boolean(sourceUpdating) || source.url === report.selected_source?.url} onClick={() => handleCorrection(source.url)}>{sourceUpdating === source.url ? 'Checking this source…' : source.url === report.selected_source?.url ? 'Current source' : 'Check this source'}</button></li>)}</ul></details>}
                <div className="source-correction"><label htmlFor="source-url">Know the original study?</label><p className="field-help">Add its public research URL. StudyLens will check the page text before showing it as a source.</p><div className="source-correction-row"><input id="source-url" type="url" placeholder="https://arxiv.org/abs/…" value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} /><button className="secondary-button" disabled={Boolean(sourceUpdating) || !sourceUrl.trim()} onClick={() => handleCorrection(sourceUrl.trim())}>{sourceUpdating === sourceUrl.trim() ? 'Checking…' : 'Check source'}</button></div></div>
                {report.corrections.length > 0 && <details className="trace-list"><summary>Source corrections ({report.corrections.length})</summary><ol>{report.corrections.map((item, index) => <li key={index}>Checked <a href={item.new_url} target="_blank" rel="noopener noreferrer">{item.new_url}</a>{item.previous_url ? ` after ${item.previous_url}` : ''}</li>)}</ol></details>}
                <div className="report-actions"><button className="secondary-button" onClick={shareReport}>{copied ? 'Link copied' : 'Copy report link'}</button><span>Saved {new Date(report.created_at).toLocaleDateString()}</span></div>
                <details className="trace-list"><summary>How this investigation was made</summary><ol>{report.trace.map((step, index) => <li key={index}>{step}</li>)}</ol><p>Model output can be mistaken. Check the original source before sharing a conclusion.</p></details>
              </div>
            ) : (
              <div className="empty-evidence"><div className="evidence-spine"><span /><span /><span /></div><p>{stage === 'investigating' ? 'Searching research sources and checking the original text…' : stage === 'extracting' ? 'Reading the claim so you can confirm it…' : stage === 'review' ? 'Confirm the wording, then trace it to its source.' : 'The source trail will appear here, with passages you can open and inspect.'}</p></div>
            )}
          </section>
        </div>
      </main>

      <footer className="footer"><span>StudyLens is an evidence trail, not a verdict.</span><span>Built for the Nebius × NVIDIA Global AI Hackathon</span></footer>
    </div>
  )
}

export default App
