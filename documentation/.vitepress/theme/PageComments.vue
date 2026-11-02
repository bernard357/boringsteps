<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useData, useRoute, withBase } from 'vitepress'

// Comments below a post, backed by the serverless API in comments/.
// Settings come from vite.define (__COMMENTS__), never from themeConfig, so
// they live in the JS bundle and not in the server-rendered HTML. The widget
// renders nothing unless all three settings are set and the page is a post.
const config = typeof __COMMENTS__ !== 'undefined' ? __COMMENTS__ : {}
const apiUrl = (config.apiUrl || '').replace(/\/+$/, '')
const cognitoDomain = (config.cognitoDomain || '')
  .replace(/^[a-z]+:\/\//i, '')
  .replace(/\/+$/, '')
const clientId = config.clientId || ''

const MAX_LENGTH = 2000
const SLUG_RE = /^[a-z0-9][a-z0-9-]{0,99}$/
const KEY_SESSION = 'comments.session'
const KEY_VERIFIER = 'comments.verifier'
const KEY_STATE = 'comments.state'
const KEY_RETURN = 'comments.returnTo'
const MODERATION_ACTIONS = [
  { status: 'approved', label: 'Approve' },
  { status: 'hidden', label: 'Hide' },
  { status: 'pending', label: 'Set pending' },
]

const route = useRoute()
const { frontmatter } = useData()

const enabled = computed(() =>
  Boolean(apiUrl && cognitoDomain && clientId && frontmatter.value.date),
)

const session = ref(null)
const comments = ref([])
const loading = ref(false)
const busy = ref(false)
const status = ref('')
const draft = ref('')
const replyTo = ref(null)
const replyDraft = ref('')
let loadToken = 0

const isModerator = computed(() =>
  Boolean(session.value && session.value.groups.includes('moderators')),
)

// Top-level comments with their replies; replies to unknown parents dropped.
const threads = computed(() => {
  const tops = comments.value.filter((c) => !c.parent_id)
  const ids = new Set(tops.map((c) => c.id))
  const replies = {}
  for (const c of comments.value) {
    if (c.parent_id && ids.has(c.parent_id)) {
      ;(replies[c.parent_id] ||= []).push(c)
    }
  }
  return tops.map((c) => ({ ...c, replies: replies[c.id] || [] }))
})

function stripBase(path) {
  const base = withBase('/')
  return path.startsWith(base) ? '/' + path.slice(base.length) : path
}

function currentSlug() {
  // Route path like /hello-boring-world.html or /hello-boring-world
  return stripBase(route.path)
    .replace(/\.html$/, '')
    .replace(/\/$/, '')
    .replace(/^\//, '')
}

function callbackUrl() {
  return `${location.origin}/comments-callback.html`
}

function base64url(bytes) {
  let binary = ''
  for (const b of bytes) binary += String.fromCharCode(b)
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

function randomString(size) {
  return base64url(crypto.getRandomValues(new Uint8Array(size)))
}

async function codeChallenge(verifier) {
  const data = new TextEncoder().encode(verifier)
  const digest = await crypto.subtle.digest('SHA-256', data)
  return base64url(new Uint8Array(digest))
}

// Read the JWT payload for display only; the API verifies the token.
function decodePayload(token) {
  const part = (token.split('.')[1] || '').replace(/-/g, '+').replace(/_/g, '/')
  const padded = part + '='.repeat((4 - (part.length % 4)) % 4)
  const bytes = Uint8Array.from(atob(padded), (ch) => ch.charCodeAt(0))
  return JSON.parse(new TextDecoder().decode(bytes))
}

function sessionFrom(idToken) {
  const claims = decodePayload(idToken)
  let name = claims.name || claims.preferred_username || 'Reader'
  if (String(name).includes('@')) name = 'Reader'
  const groups = Array.isArray(claims['cognito:groups'])
    ? claims['cognito:groups']
    : []
  return { idToken, exp: Number(claims.exp) || 0, name, groups }
}

function sessionValid() {
  return Boolean(session.value && session.value.exp * 1000 > Date.now())
}

function clearSession() {
  session.value = null
  try {
    sessionStorage.removeItem(KEY_SESSION)
  } catch {
    // Storage unavailable: nothing to clear.
  }
}

function restoreSession() {
  try {
    const raw = sessionStorage.getItem(KEY_SESSION)
    if (!raw) return
    const stored = JSON.parse(raw)
    session.value = sessionFrom(stored.idToken)
  } catch {
    session.value = null
  }
  if (!sessionValid()) clearSession()
}

function storeSession(idToken) {
  session.value = sessionFrom(idToken)
  // Keep only the ID token and its expiry; no refresh token, no cookies.
  sessionStorage.setItem(
    KEY_SESSION,
    JSON.stringify({ idToken, exp: session.value.exp }),
  )
}

async function signIn() {
  const verifier = randomString(32)
  const state = randomString(16)
  sessionStorage.setItem(KEY_VERIFIER, verifier)
  sessionStorage.setItem(KEY_STATE, state)
  sessionStorage.setItem(KEY_RETURN, route.path)
  const params = new URLSearchParams({
    response_type: 'code',
    client_id: clientId,
    redirect_uri: callbackUrl(),
    scope: 'openid email profile',
    state,
    code_challenge: await codeChallenge(verifier),
    code_challenge_method: 'S256',
  })
  location.assign(`https://${cognitoDomain}/oauth2/authorize?${params}`)
}

function signOut() {
  clearSession()
  sessionStorage.setItem(KEY_RETURN, route.path)
  const params = new URLSearchParams({
    client_id: clientId,
    logout_uri: callbackUrl(),
  })
  location.assign(`https://${cognitoDomain}/logout?${params}`)
}

// Finish the sign-in when the callback page brought us back with ?code.
async function handleCallback() {
  const params = new URLSearchParams(location.search)
  const code = params.get('code')
  if (!code && !params.get('error')) return
  const expected = sessionStorage.getItem(KEY_STATE)
  const verifier = sessionStorage.getItem(KEY_VERIFIER)
  sessionStorage.removeItem(KEY_STATE)
  sessionStorage.removeItem(KEY_VERIFIER)
  history.replaceState(history.state, '', location.pathname + location.hash)
  if (!code || !verifier || !expected || params.get('state') !== expected) {
    status.value = 'Sign-in did not complete. Please try again.'
    return
  }
  try {
    const res = await fetch(`https://${cognitoDomain}/oauth2/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({
        grant_type: 'authorization_code',
        client_id: clientId,
        code,
        redirect_uri: callbackUrl(),
        code_verifier: verifier,
      }),
    })
    if (!res.ok) throw new Error(`token ${res.status}`)
    const data = await res.json()
    storeSession(data.id_token)
    status.value = `Signed in as ${session.value.name}.`
  } catch {
    clearSession()
    status.value = 'Sign-in failed. Please try again.'
  }
}

function authHeaders() {
  return { Authorization: `Bearer ${session.value.idToken}` }
}

async function load() {
  const token = ++loadToken
  comments.value = []
  replyTo.value = null
  if (!enabled.value) return
  const slug = currentSlug()
  if (!SLUG_RE.test(slug)) return
  if (session.value && !sessionValid()) clearSession()
  loading.value = true
  try {
    const moderate = isModerator.value
    const path = moderate ? 'moderation' : 'comments'
    let res = await fetch(`${apiUrl}/posts/${slug}/${path}`, {
      headers: moderate ? authHeaders() : {},
    })
    if (moderate && res.status === 401) {
      clearSession()
      res = await fetch(`${apiUrl}/posts/${slug}/comments`)
    }
    if (!res.ok) throw new Error(`load ${res.status}`)
    const data = await res.json()
    if (token === loadToken) comments.value = data.comments || []
  } catch {
    if (token === loadToken) status.value = 'Comments could not be loaded.'
  } finally {
    if (token === loadToken) loading.value = false
  }
}

async function errorMessage(res) {
  if (res.status === 401) {
    clearSession()
    return 'Your session has expired. Please sign in again.'
  }
  if (res.status === 429) {
    return 'Too many comments in a short time. Please try again later.'
  }
  try {
    const data = await res.json()
    if (data && typeof data.message === 'string') return data.message
  } catch {
    // Not JSON: fall through to the generic message.
  }
  return 'Something went wrong. Please try again.'
}

async function submit(parentId) {
  const text = (parentId ? replyDraft.value : draft.value).trim()
  if (!text) return
  if (!sessionValid()) {
    clearSession()
    status.value = 'Please sign in to comment.'
    return
  }
  busy.value = true
  try {
    const body = parentId ? { text, parent_id: parentId } : { text }
    const res = await fetch(`${apiUrl}/posts/${currentSlug()}/comments`, {
      method: 'POST',
      headers: { ...authHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!res.ok) {
      status.value = await errorMessage(res)
      return
    }
    const created = await res.json()
    if (parentId) {
      replyDraft.value = ''
      replyTo.value = null
    } else {
      draft.value = ''
    }
    status.value =
      created.status === 'pending'
        ? 'Thanks. Your comment is waiting for moderation.'
        : 'Your comment is published.'
    await load()
  } catch {
    status.value = 'Something went wrong. Please try again.'
  } finally {
    busy.value = false
  }
}

async function moderate(comment, newStatus) {
  if (!sessionValid()) {
    clearSession()
    status.value = 'Your session has expired. Please sign in again.'
    return
  }
  busy.value = true
  try {
    const slug = currentSlug()
    const res = await fetch(`${apiUrl}/posts/${slug}/comments/${comment.id}`, {
      method: 'PATCH',
      headers: { ...authHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: newStatus }),
    })
    if (!res.ok) {
      status.value = await errorMessage(res)
      return
    }
    status.value = `Comment by ${comment.author_name} set to ${newStatus}.`
    await load()
  } catch {
    status.value = 'Something went wrong. Please try again.'
  } finally {
    busy.value = false
  }
}

function startReply(comment) {
  replyTo.value = comment.id
  replyDraft.value = ''
}

function formatDate(iso) {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short' })
}

onMounted(async () => {
  // The widget stays mounted across client-side navigation, so restore the
  // session even on a non-post page; later route changes reuse it.
  restoreSession()
  if (!enabled.value) return
  await handleCallback()
  await load()
})
watch(
  () => route.path,
  () => {
    status.value = ''
    load()
  },
)
</script>

<template>
  <section v-if="enabled" class="page-comments" aria-label="Comments">
    <h2 class="page-comments-title">Comments</h2>
    <p class="page-comments-notice" role="status" aria-live="polite">{{ status }}</p>

    <p v-if="loading" class="page-comments-empty">Loading comments…</p>
    <p v-else-if="!threads.length" class="page-comments-empty">No comments yet.</p>

    <ol v-if="threads.length" class="page-comments-list">
      <li v-for="thread in threads" :key="thread.id" class="page-comments-item">
        <div class="page-comments-meta">
          <span class="page-comments-author">{{ thread.author_name }}</span>
          <time :datetime="thread.created_at">{{ formatDate(thread.created_at) }}</time>
          <span
            v-if="thread.status && thread.status !== 'approved'"
            class="page-comments-status"
          >{{ thread.status }}</span>
        </div>
        <p class="page-comments-text">{{ thread.text }}</p>
        <div v-if="session" class="page-comments-actions">
          <button
            v-if="(thread.status || 'approved') === 'approved'"
            type="button"
            class="page-comments-button"
            :disabled="busy"
            @click="startReply(thread)"
          >Reply</button>
          <template v-if="isModerator">
            <button
              v-for="action in MODERATION_ACTIONS.filter((a) => a.status !== thread.status)"
              :key="action.status"
              type="button"
              class="page-comments-button"
              :disabled="busy"
              @click="moderate(thread, action.status)"
            >{{ action.label }}</button>
          </template>
        </div>

        <form
          v-if="replyTo === thread.id"
          class="page-comments-form"
          @submit.prevent="submit(thread.id)"
        >
          <label :for="`page-comments-reply-${thread.id}`">
            Reply to {{ thread.author_name }}
          </label>
          <textarea
            :id="`page-comments-reply-${thread.id}`"
            v-model="replyDraft"
            rows="3"
            :maxlength="MAX_LENGTH"
            required
          ></textarea>
          <div class="page-comments-actions">
            <button type="submit" class="page-comments-button" :disabled="busy">
              Post reply
            </button>
            <button
              type="button"
              class="page-comments-button"
              :disabled="busy"
              @click="replyTo = null"
            >Cancel</button>
          </div>
        </form>

        <ol v-if="thread.replies.length" class="page-comments-list">
          <li
            v-for="reply in thread.replies"
            :key="reply.id"
            class="page-comments-item page-comments-reply"
          >
            <div class="page-comments-meta">
              <span class="page-comments-author">{{ reply.author_name }}</span>
              <time :datetime="reply.created_at">{{ formatDate(reply.created_at) }}</time>
              <span
                v-if="reply.status && reply.status !== 'approved'"
                class="page-comments-status"
              >{{ reply.status }}</span>
            </div>
            <p class="page-comments-text">{{ reply.text }}</p>
            <div v-if="isModerator" class="page-comments-actions">
              <button
                v-for="action in MODERATION_ACTIONS.filter((a) => a.status !== reply.status)"
                :key="action.status"
                type="button"
                class="page-comments-button"
                :disabled="busy"
                @click="moderate(reply, action.status)"
              >{{ action.label }}</button>
            </div>
          </li>
        </ol>
      </li>
    </ol>

    <form v-if="session" class="page-comments-form" @submit.prevent="submit(null)">
      <label for="page-comments-text">Your comment</label>
      <textarea
        id="page-comments-text"
        v-model="draft"
        rows="4"
        :maxlength="MAX_LENGTH"
        required
      ></textarea>
      <div class="page-comments-actions">
        <button type="submit" class="page-comments-button" :disabled="busy">
          Post comment
        </button>
        <span class="page-comments-signed">Signed in as {{ session.name }}</span>
        <button type="button" class="page-comments-button" @click="signOut">
          Sign out
        </button>
      </div>
    </form>
    <div v-else class="page-comments-actions">
      <button type="button" class="page-comments-button" @click="signIn">
        Sign in to comment
      </button>
      <span class="page-comments-signed">
        With GitHub, Google, Amazon, Facebook or LinkedIn.
      </span>
    </div>
  </section>
</template>
