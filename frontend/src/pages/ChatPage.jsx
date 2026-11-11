import React, { useEffect, useRef, useState } from 'react'
import toast from 'react-hot-toast'
import { useNoteStore } from '../store/noteStore'
import {
  createConversation,
  getConversationMessages,
  getConversations,
  sendChatMessage,
} from '../utils/api'

function responseError(error, fallback) {
  return error?.response?.data?.error || fallback
}

export default function ChatPage() {
  const documentId = useNoteStore((state) => state.documentId)
  const setDocumentId = useNoteStore((state) => state.setDocumentId)
  const setDocumentTitle = useNoteStore((state) => state.setDocumentTitle)
  const setActiveView = useNoteStore((state) => state.setActiveView)
  const [conversations, setConversations] = useState([])
  const [conversationId, setConversationId] = useState(null)
  const [messages, setMessages] = useState([])
  const [draft, setDraft] = useState('')
  const [loadingHistory, setLoadingHistory] = useState(true)
  const [sending, setSending] = useState(false)
  const messageListRef = useRef(null)

  useEffect(() => {
    let active = true
    setLoadingHistory(true)
    setConversationId(null)
    setMessages([])

    getConversations()
      .then(async ({ data }) => {
        if (!active) return
        const items = data.conversations || []
        setConversations(items)
        const selected = documentId ? items.find((item) => item.doc_id === documentId) : items[0]
        if (!selected) return
        setConversationId(selected.id)
        if (!documentId && selected.doc_id) {
          setDocumentId(selected.doc_id)
          setDocumentTitle(selected.document_name || '')
        }
        const history = await getConversationMessages(selected.id)
        if (active) setMessages(history.data.messages || [])
      })
      .catch((error) => {
        if (active) toast.error(responseError(error, 'Could not load conversation history'))
      })
      .finally(() => {
        if (active) setLoadingHistory(false)
      })

    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    const list = messageListRef.current
    if (list) list.scrollTop = list.scrollHeight
  }, [messages, sending])

  const selectConversation = async (conversation) => {
    setConversationId(conversation.id)
    setMessages([])
    if (conversation.doc_id && conversation.doc_id !== documentId) {
      setDocumentId(conversation.doc_id)
      setDocumentTitle(conversation.document_name || '')
    }
    try {
      const response = await getConversationMessages(conversation.id)
      setMessages(response.data.messages || [])
    } catch (error) {
      toast.error(responseError(error, 'Could not open this conversation'))
    }
  }

  const startConversation = async () => {
    if (!documentId) {
      toast.error('Upload or select a document before starting a chat')
      return
    }
    try {
      const response = await createConversation(documentId)
      const conversation = response.data.conversation
      setConversations((items) => [conversation, ...items])
      setConversationId(conversation.id)
      setMessages([])
    } catch (error) {
      toast.error(responseError(error, 'Could not start a conversation'))
    }
  }

  const submitMessage = async (event) => {
    event.preventDefault()
    const question = draft.trim()
    if (!question || sending) return

    setSending(true)
    setDraft('')
    const optimisticId = `pending-${Date.now()}`
    setMessages((items) => [...items, {
      id: optimisticId,
      role: 'user',
      content: question,
      citations: [],
    }])

    try {
      let activeConversationId = conversationId
      if (!activeConversationId) {
        if (!documentId) throw new Error('Upload or select a document before asking a question')
        const created = await createConversation(documentId)
        const conversation = created.data.conversation
        activeConversationId = conversation.id
        setConversationId(activeConversationId)
        setConversations((items) => [conversation, ...items])
      }

      const response = await sendChatMessage(activeConversationId, question)
      const { user_message: userMessage, assistant_message: assistantMessage } = response.data
      setMessages((items) => [
        ...items.filter((message) => message.id !== optimisticId),
        userMessage,
        assistantMessage,
      ])
      setConversations((items) => items.map((item) => (
        item.id === activeConversationId
          ? { ...item, title: item.title === 'New conversation' ? question : item.title }
          : item
      )))
    } catch (error) {
      setMessages((items) => items.filter((message) => message.id !== optimisticId))
      setDraft(question)
      toast.error(responseError(error, error.message || 'The assistant could not answer'))
    } finally {
      setSending(false)
    }
  }

  return (
    <main className="flex min-h-full flex-col">
      <header className="mb-6">
        <p className="mb-2 text-sm font-semibold" style={{ color: 'var(--ink)' }}>Document assistant</p>
        <h1>Ask your notes.</h1>
        <p className="page-description">Get grounded answers with page references. Follow-up questions stay in the same conversation.</p>
      </header>

      <div className="grid min-h-[480px] flex-1 gap-5 lg:grid-cols-[240px_minmax(0,1fr)]">
        <aside className="surface flex flex-col gap-3 p-4" aria-label="Conversation history">
          <button type="button" className="btn-secondary w-full px-4 py-2.5" onClick={startConversation}>
            New conversation
          </button>
          <p className="m-0 px-1 text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--ink-soft)' }}>
            Recent conversations
          </p>
          <div className="flex min-h-0 flex-col gap-1 overflow-y-auto">
            {conversations.map((conversation) => (
              <button
                type="button"
                key={conversation.id}
                onClick={() => selectConversation(conversation)}
                className="rounded-[var(--radius-sm)] px-3 py-2 text-left text-sm"
                style={{
                  background: conversation.id === conversationId ? 'var(--accent-15)' : 'transparent',
                  border: '1px solid var(--line)',
                  color: 'var(--ink)',
                }}
              >
                <span className="block overflow-hidden text-ellipsis whitespace-nowrap">{conversation.title}</span>
                <span className="mt-1 block overflow-hidden text-ellipsis whitespace-nowrap text-xs" style={{ color: 'var(--ink-soft)' }}>
                  {conversation.document_name || 'Document unavailable'}
                </span>
              </button>
            ))}
            {!loadingHistory && conversations.length === 0 && (
              <p className="px-1 text-sm" style={{ color: 'var(--ink-soft)' }}>Your conversations will appear here.</p>
            )}
          </div>
        </aside>

        <section className="surface flex min-h-[480px] flex-col overflow-hidden" aria-label="Chat messages">
          <div ref={messageListRef} className="flex flex-1 flex-col gap-4 overflow-y-auto p-5">
            {loadingHistory && <p role="status" style={{ color: 'var(--ink-soft)' }}>Loading conversations…</p>}
            {!loadingHistory && messages.length === 0 && (
              <div className="m-auto max-w-md text-center">
                <h2 className="m-0 text-2xl">Start with a question</h2>
                <p className="page-description">
                  {documentId
                    ? 'Answers are grounded in your current document and include page citations when available.'
                    : 'Choose an earlier conversation or upload a document in the Workspace to begin.'}
                </p>
                {!documentId && (
                  <button type="button" className="btn-primary mt-4 px-5 py-2.5" onClick={() => setActiveView('summarize')}>
                    Go to Workspace
                  </button>
                )}
              </div>
            )}
            {messages.map((message) => (
              <article
                key={message.id}
                className="max-w-[88%] rounded-[var(--radius-md)] p-4"
                style={{
                  alignSelf: message.role === 'user' ? 'flex-end' : 'flex-start',
                  background: message.role === 'user' ? 'var(--accent-15)' : 'var(--paper)',
                  border: '1px solid var(--line)',
                  color: 'var(--ink)',
                }}
              >
                <p className="m-0 whitespace-pre-wrap leading-relaxed">{message.content}</p>
                {message.role === 'assistant' && message.citations?.length > 0 && (
                  <p className="mb-0 mt-3 text-xs font-semibold" style={{ color: 'var(--accent)' }}>
                    Sources: {message.citations.map((page) => `Page ${page}`).join(', ')}
                  </p>
                )}
              </article>
            ))}
            {sending && <p role="status" className="m-0 text-sm" style={{ color: 'var(--ink-soft)' }}>Searching your document…</p>}
          </div>

          <form onSubmit={submitMessage} className="flex items-end gap-3 border-t p-4" style={{ borderColor: 'var(--line)' }}>
            <label className="sr-only" htmlFor="chat-message">Ask a question about this document</label>
            <textarea
              id="chat-message"
              name="message"
              rows={2}
              maxLength={5000}
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault()
                  event.currentTarget.form?.requestSubmit()
                }
              }}
              placeholder="Ask a question about your document…"
              className="min-h-[54px] flex-1 resize-y rounded-[var(--radius-sm)] border bg-transparent px-3 py-2.5 text-sm outline-none"
              style={{ borderColor: 'var(--line)', color: 'var(--ink)' }}
              disabled={sending}
            />
            <button type="submit" className="btn-primary shrink-0 px-5 py-2.5" disabled={sending || !draft.trim()}>
              {sending ? 'Thinking…' : 'Send'}
            </button>
          </form>
        </section>
      </div>
    </main>
  )
}
