/**
 * In-app documentation.
 *
 * Served by the app rather than linking out to the GitHub README: a new
 * operator is already signed in here, and sending them to a repository they
 * may not have access to is a dead end. The README stays authoritative for
 * developers; this covers using the tool.
 */
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { H1, H2, SUB } from '../ui'

interface Section {
  id: string
  title: string
  body: React.ReactNode
}

/** Numbered step with a hairline rule down the left. */
function Step({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <li className="relative border-l border-line pb-6 pl-6 last:pb-0">
      <span className="absolute -left-[11px] top-0 flex h-[22px] w-[22px] items-center justify-center border border-line bg-ink-900 text-[12px] text-violet-300">
        {n}
      </span>
      <p className="text-[16px] text-mist-50">{title}</p>
      <div className="mt-2 space-y-2 text-[15px] leading-[1.65] text-mist-500">{children}</div>
    </li>
  )
}

function Code({ children }: { children: React.ReactNode }) {
  return (
    <code className="border border-line bg-ink-800 px-1.5 py-0.5 text-[14px] break-all text-mist-200">
      {children}
    </code>
  )
}

const SECTIONS: Section[] = [
  {
    id: 'getting-started',
    title: 'Getting started',
    body: (
      <>
        <p className="text-[16px] leading-[1.65] text-mist-500">
          The tool publishes video to LinkedIn on your behalf. It never sees or stores a
          password — you grant it publishing rights through LinkedIn&rsquo;s own consent
          screen, and you can withdraw them at any time from your LinkedIn settings.
        </p>
        <ol className="mt-6 space-y-0">
          <Step n={1} title="Connect LinkedIn">
            <p>
              Open <Link to="/settings" className="text-violet-300 underline underline-offset-2">Settings</Link>{' '}
              and choose <em>Reconnect LinkedIn</em>. Consent opens in a new tab and closes
              itself when it is done. If your account is new, an administrator has to approve
              it before anything else works.
            </p>
          </Step>
          <Step n={2} title="Upload a reel">
            <p>
              MP4, MOV, AVI, MKV or WEBM, up to 90 seconds and 500 MB. The file is checked in
              the browser before the upload starts, so an unusable file fails immediately
              rather than after a long transfer.
            </p>
          </Step>
          <Step n={3} title="Write a caption and choose a time">
            <p>
              Publish immediately, or pick a time and let the scheduler do it. Scheduled posts
              appear in the Queue with their status.
            </p>
          </Step>
        </ol>
      </>
    ),
  },
  {
    id: 'linkedin-app',
    title: 'Setting up your own LinkedIn app',
    body: (
      <>
        <p className="text-[16px] leading-[1.65] text-mist-500">
          Only needed if you are running your own copy of this tool. If someone else hosts it
          for you, skip this — the app is already registered.
        </p>
        <ol className="mt-6 space-y-0">
          <Step n={1} title="Create the app">
            <p>
              At{' '}
              <a
                href="https://www.linkedin.com/developers/apps/new"
                target="_blank"
                rel="noreferrer"
                className="text-violet-300 underline underline-offset-2"
              >
                linkedin.com/developers
              </a>
              . A LinkedIn <em>company page</em> is required — you can create one in a minute
              if you do not have it, and it does not have to be a real company.
            </p>
          </Step>
          <Step n={2} title="Request the two products">
            <p>
              On the Products tab, add <strong className="text-mist-200">Sign In with LinkedIn
              using OpenID Connect</strong> and <strong className="text-mist-200">Share on
              LinkedIn</strong>. The first grants <Code>openid profile</Code>, the second{' '}
              <Code>w_member_social</Code>. Without both, sign-in works but publishing fails.
            </p>
            <p>Approval is usually instant, but can take a few minutes to appear.</p>
          </Step>
          <Step n={3} title="Add the redirect URL">
            <p>
              On the Auth tab, under <em>Authorized redirect URLs</em>, add the callback for
              wherever the tool runs. It must match <strong className="text-mist-200">exactly</strong>,
              including protocol and port:
            </p>
            <p>
              <Code>http://localhost:5000/api/auth/linkedin/callback</Code>
            </p>
            <p>Add one entry per environment you use — local and deployed are different URLs.</p>
          </Step>
          <Step n={4} title="Copy the credentials">
            <p>
              From the Auth tab, copy the Client ID and Client Secret into <Code>.env</Code> as{' '}
              <Code>LINKEDIN_CLIENT_ID</Code> and <Code>LINKEDIN_CLIENT_SECRET</Code>, then
              restart the server.
            </p>
          </Step>
        </ol>
      </>
    ),
  },
  {
    id: 'limits',
    title: 'Limits',
    body: (
      <dl className="divide-y divide-line">
        {[
          ['Formats', 'MP4, MOV, AVI, MKV, WEBM'],
          ['Duration', 'Up to 90 seconds'],
          ['File size', 'Up to 500 MB'],
          ['Authentication', 'OAuth only — no passwords are stored'],
        ].map(([k, v]) => (
          <div key={k} className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1 py-3">
            <dt className="text-[15px] text-mist-500">{k}</dt>
            <dd className="text-[15px] text-mist-50">{v}</dd>
          </div>
        ))}
      </dl>
    ),
  },
  {
    id: 'troubleshooting',
    title: 'Troubleshooting',
    body: (
      <dl className="space-y-5">
        {[
          {
            q: '“Account Pending” after signing in',
            a: 'Your account exists but has not been approved. An administrator has to activate it from the Admin panel. This is deliberate — new sign-ups cannot use the tool until someone lets them in.',
          },
          {
            q: 'Sign-in returns to the landing page with an error',
            a: 'Almost always a redirect URL mismatch. The URL in your LinkedIn app\'s Auth tab has to match the one the server is using character for character, including http vs https and the port.',
          },
          {
            q: 'Publishing fails but sign-in works',
            a: 'The Share on LinkedIn product is probably missing, so the token has no w_member_social scope. Add the product, then reconnect from Settings — an existing token does not gain scopes on its own.',
          },
          {
            q: 'Token expired',
            a: 'LinkedIn access tokens lapse. Reconnect from Settings; nothing else is lost, and scheduled posts resume.',
          },
          {
            q: '“A network error occurred while communicating with LinkedIn”',
            a: 'The server could not reach LinkedIn. If the logs show an SSL error against api.linkedin.com while www.linkedin.com works, the network is filtering that hostname — some ISPs, office networks and antivirus HTTPS scanners do. Sign-in itself no longer needs that host, but publishing does, so try a different network or a phone hotspot.',
          },
        ].map(({ q, a }) => (
          <div key={q}>
            <dt className="text-[16px] text-mist-50">{q}</dt>
            <dd className="mt-1.5 text-[15px] leading-[1.65] text-mist-500">{a}</dd>
          </div>
        ))}
      </dl>
    ),
  },
]

export default function Docs() {
  const [active, setActive] = useState(SECTIONS[0].id)

  return (
    <div className="mx-auto max-w-5xl animate-rise-in">
      <h1 className={H1}>Documentation</h1>
      <p className={SUB}>How to connect an account, publish, and fix the usual problems.</p>

      <div className="mt-10 gap-10 lg:grid lg:grid-cols-[190px_1fr]">
        {/* Horizontal scroller on phones, sticky rail on desktop. */}
        <nav className="-mx-7 mb-8 overflow-x-auto px-7 lg:sticky lg:top-24 lg:mx-0 lg:mb-0 lg:self-start lg:overflow-visible lg:px-0">
          <ul className="flex gap-1 lg:flex-col">
            {SECTIONS.map((s) => (
              <li key={s.id}>
                <a
                  href={`#${s.id}`}
                  onClick={() => setActive(s.id)}
                  className={`block border-l-2 px-3 py-2 text-[15px] whitespace-nowrap transition lg:whitespace-normal ${
                    active === s.id
                      ? 'border-violet-500 text-mist-50'
                      : 'border-transparent text-mist-500 hover:text-mist-50'
                  }`}
                >
                  {s.title}
                </a>
              </li>
            ))}
          </ul>
        </nav>

        <div className="min-w-0 space-y-3">
          {SECTIONS.map((s) => (
            <section key={s.id} id={s.id} className="surface scroll-mt-24 p-6 sm:p-8">
              <h2 className={`${H2} text-[24px]`}>{s.title}</h2>
              <div className="mt-6">{s.body}</div>
            </section>
          ))}
        </div>
      </div>
    </div>
  )
}
