// haiku-resta-haiku: when the model that starts a subagent (the main session or a subagent itself) is Haiku, the
// subagent runs on Haiku whatever model Claude asked for, so the whole tree stays on the local Strata server that the
// gateway serves Haiku from. Sessions on other models (Opus, Sonnet) are left as they are.

const isHaiku = (model) => typeof model === 'string' && model.toLowerCase().includes('haiku')

export function register(on) {
  on('agent.spawn', async ($, e, next) => {
    // parentModel: the model of whoever starts the subagent; fall back to the main loop's model
    const parent = e.parentModel || (await $.session.model())
    if (!isHaiku(parent)) return next(e)
    if (e.model !== undefined && e.model !== 'inherit' && !isHaiku(e.model))
      $.ui.toast('haiku-resta-haiku: sotto-agente ' + e.subagentType + ' chiesto su ' + e.model + ', avviato su Haiku')
    return next({ ...e, model: 'haiku' })
  })
}
