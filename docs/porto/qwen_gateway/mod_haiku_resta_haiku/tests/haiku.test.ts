import { expect, test } from 'claude-code/testing'

const base = { prompt: 'p', description: 'd', subagentType: 'general-purpose', background: false, fork: false }

test('a Haiku parent starts its subagents on Haiku, whatever model Claude asked for', async ($, on) => {
  const seen: (string | undefined)[] = []
  on('agent.spawn', ($, e) => { seen.push(e.model); return { model: e.model ?? 'inherit' } })
  await $.agent.spawn({ ...base, parentModel: 'claude-haiku-4-5-20251001', model: 'opus' } as any)
  await $.agent.spawn({ ...base, parentModel: 'claude-haiku-4-5-20251001' } as any)
  await $.agent.spawn({ ...base, parentModel: 'haiku', model: 'sonnet' } as any)
  expect(seen).toEqual(['haiku', 'haiku', 'haiku'])
})

test('an Opus parent is left alone', async ($, on) => {
  const seen: (string | undefined)[] = []
  on('agent.spawn', ($, e) => { seen.push(e.model); return { model: e.model ?? 'inherit' } })
  await $.agent.spawn({ ...base, parentModel: 'claude-opus-5-5', model: 'sonnet' } as any)
  await $.agent.spawn({ ...base, parentModel: 'claude-opus-5-5' } as any)
  expect(seen).toEqual(['sonnet', undefined])
})
