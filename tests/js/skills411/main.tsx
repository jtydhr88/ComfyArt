// #411: Skills-create tip CSS harness — real SkillForm markup classes + menus/dialogs. $0 mocks.
import { createRoot } from 'react-dom/client'
import { Icons } from '../../../src/ui/icons'
import { setLang, t } from '../i18n_stub'

const q = new URLSearchParams(location.search)
const lang = q.get('lang') === 'en' ? 'en' : 'zh'
setLang(lang)
if (q.get('theme') === 'dark') document.documentElement.dataset.theme = 'dark'

const SAMPLE = {
  id: 'demo1',
  name: lang === 'en' ? 'Morning coffee poster' : '早安咖啡店海报',
  instructions: lang === 'en'
    ? 'Vertical warm coffee-shop morning poster. Title on top. Aspect 3:4. Offer 2 directions.'
    : '竖版暖色调咖啡店早安海报，标题置顶，比例 3:4，给 2 个方向。',
  files: { 'notes.md': '# notes\nkeep margins' },
  images: {} as Record<string, string>,
  custom: true as const,
}

function MenuSkills() {
  return (
    <div className="ca-menu ca-skills" data-testid="menu-skills">
      <button type="button" className="ca-menu__item">
        <span className="ca-icon">{Icons.plus}</span><span className="ca-menu__grow">{t('composer.skillCreator')}</span>
      </button>
      <button type="button" className="ca-menu__item">
        <span className="ca-icon">{Icons.agent}</span><span className="ca-menu__grow">{t('composer.createSkillFromThisChat')}</span>
      </button>
      <button type="button" className="ca-menu__item">
        <span className="ca-icon">{Icons.files}</span><span className="ca-menu__grow">{t('composer.manageSkills')}</span>
      </button>
      <div className="ca-menu__sep" />
      <button type="button" className="ca-menu__item">
        <span className="ca-menu__grow">{SAMPLE.name}</span>
        <span className="ca-menu__key">{t('composer.personal')}</span>
      </button>
      <button type="button" className="ca-menu__item">
        <span className="ca-menu__grow">{t('skills.posterDesign')}</span>
      </button>
    </div>
  )
}

function SkillFormEmpty() {
  return (
    <div className="ca-menu ca-skilled" data-testid="form-empty">
      <div className="ca-gen__title">{t('composer.skillCreator')}</div>
      <div className="ca-rename__body">
        <input className="ca-panel__input" value="" placeholder={t('composer.skillName')} readOnly />
        <div className="ca-gen__label">SKILL.md</div>
        <textarea className="ca-panel__prompt ca-panel__prompt--boxed ca-skills__md" value="" placeholder={t('composer.instructionsForTheAgentDeliverables')} readOnly />
        <div className="ca-gen__label">{t('skillsDialog.attachedFiles')}</div>
        <button type="button" className="ca-lib__new"><span className="ca-icon">{Icons.upload}</span>{t('skillsDialog.addFile')}</button>
        <div className="ca-gen__label">{t('common.image')}</div>
        <div className="ca-gen__refs ca-lib__images">
          <button type="button" className="ca-gen__refadd"><span className="ca-icon">{Icons.plus}</span><span>{t('skillsDialog.addImage')}</span></button>
        </div>
        <div className="ca-panel__foot">
          <button type="button" className="ca-panel__secondary">{t('common.cancel')}</button>
          <button type="button" className="ca-panel__primary" disabled>{t('common.save')}</button>
        </div>
      </div>
    </div>
  )
}

function SkillFormFilled() {
  return (
    <div className="ca-menu ca-skilled" data-testid="form-filled">
      <div className="ca-gen__title">{t('composer.skillCreator')}</div>
      <div className="ca-rename__body">
        <input className="ca-panel__input" value={SAMPLE.name} readOnly />
        <div className="ca-gen__label">SKILL.md</div>
        <textarea className="ca-panel__prompt ca-panel__prompt--boxed ca-skills__md" value={SAMPLE.instructions} readOnly />
        <div className="ca-gen__label">{t('skillsDialog.attachedFiles')}</div>
        <div className="ca-skills__file">
          <div className="ca-memory__row">
            <span className="ca-icon">{Icons.files}</span>
            <span className="ca-menu__grow">notes.md</span>
            <button type="button" className="ca-history__del" title={t('common.remove')}>{Icons.trash}</button>
          </div>
        </div>
        <button type="button" className="ca-lib__new"><span className="ca-icon">{Icons.upload}</span>{t('skillsDialog.addFile')}</button>
        <div className="ca-gen__label">{t('common.image')}</div>
        <div className="ca-gen__refs ca-lib__images">
          <button type="button" className="ca-gen__refadd"><span className="ca-icon">{Icons.plus}</span><span>{t('skillsDialog.addImage')}</span></button>
        </div>
        <div className="ca-panel__foot">
          <button type="button" className="ca-panel__secondary">{t('common.cancel')}</button>
          <button type="button" className="ca-panel__primary">{t('common.save')}</button>
        </div>
      </div>
    </div>
  )
}

function DialogList({ empty }: { empty?: boolean }) {
  return (
    <div className="ca-modal" style={{ position: 'relative', inset: 'auto', background: 'transparent' }}>
      <div className="ca-modal__card ca-rename ca-memory ca-skills-dialog" data-testid={empty ? 'dialog-list-empty' : 'dialog-list'} id="scene-card">
        <div className="ca-side__head">
          <span>{t('skillsDialog.mySkills')}</span>
          <button type="button" className="ca-panel__icon" title={t('common.close')}>{Icons.close}</button>
        </div>
        <div className="ca-rename__body">
          <div className="ca-chat__hint">{t('skillsDialog.eachSkillIsAFolder')}</div>
          <div className="ca-style__row">
            <button type="button" className="ca-lib__new"><span className="ca-icon">{Icons.plus}</span>{t('skillsDialog.newSkill')}</button>
            <button type="button" className="ca-lib__new"><span className="ca-icon">{Icons.upload}</span>{t('skillsDialog.importFolder')}</button>
          </div>
          {empty ? (
            <div className="ca-side__empty">{t('skillsDialog.noPersonalSkillsYet')}</div>
          ) : (
            <div className="ca-memory__row">
              <span className="ca-icon">{Icons.skill}</span>
              <span className="ca-menu__grow">{SAMPLE.name}<span className="ca-menu__key"> · {t('skillsDialog.filesImages', 1, 0)}</span></span>
              <button type="button" className="ca-history__del" title={t('skillsDialog.use')}>{Icons.comment}</button>
              <button type="button" className="ca-history__del" title={t('common.edit')}>{Icons.textTool}</button>
              <button type="button" className="ca-history__del" title={t('skillsDialog.versionHistory')}>{Icons.undo}</button>
              <button type="button" className="ca-history__del" title={t('common.delete')}>{Icons.trash}</button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function DialogEdit() {
  return (
    <div className="ca-modal" style={{ position: 'relative', inset: 'auto', background: 'transparent' }}>
      <div className="ca-modal__card ca-rename ca-memory ca-skills-dialog" data-testid="dialog-edit" id="scene-card">
        <div className="ca-side__head">
          <span>{t('skillsDialog.editSkill')}</span>
          <button type="button" className="ca-panel__icon" title={t('common.close')}>{Icons.close}</button>
        </div>
        <div className="ca-rename__body">
          <input className="ca-panel__input" value={SAMPLE.name} readOnly />
          <div className="ca-gen__label">SKILL.md</div>
          <textarea className="ca-panel__prompt ca-panel__prompt--boxed ca-skills__md" value={SAMPLE.instructions} readOnly />
          <div className="ca-gen__label">{t('skillsDialog.attachedFiles')}</div>
          <div className="ca-skills__file">
            <div className="ca-memory__row">
              <span className="ca-icon">{Icons.files}</span>
              <span className="ca-menu__grow">notes.md</span>
              <button type="button" className="ca-history__del">{Icons.trash}</button>
            </div>
          </div>
          <button type="button" className="ca-lib__new"><span className="ca-icon">{Icons.upload}</span>{t('skillsDialog.addFile')}</button>
          <div className="ca-gen__label">{t('common.image')}</div>
          <div className="ca-gen__refs ca-lib__images">
            <button type="button" className="ca-gen__refadd"><span className="ca-icon">{Icons.plus}</span><span>{t('skillsDialog.addImage')}</span></button>
          </div>
          <div className="ca-panel__foot">
            <button type="button" className="ca-panel__secondary">{t('common.cancel')}</button>
            <button type="button" className="ca-panel__primary">{t('common.save')}</button>
          </div>
        </div>
      </div>
    </div>
  )
}

function SlashPicker() {
  return (
    <div className="ca-menu ca-skills" data-testid="slash-picker">
      <button type="button" className="ca-menu__item">
        <span className="ca-icon">{Icons.skill}</span><span className="ca-menu__grow">{SAMPLE.name}</span>
      </button>
      <button type="button" className="ca-menu__item">
        <span className="ca-icon">{Icons.skill}</span><span className="ca-menu__grow">{t('skills.posterDesign')}</span>
      </button>
      <button type="button" className="ca-menu__item">
        <span className="ca-icon">{Icons.skill}</span><span className="ca-menu__grow">{t('skills.socialMediaSet')}</span>
      </button>
    </div>
  )
}

function Chip() {
  return (
    <div className="ca-composer__chips" data-testid="skill-chip" style={{ padding: 8, width: 360 }}>
      <span className="ca-chip">
        <span className="ca-icon">{Icons.skill}</span>{SAMPLE.name}
        <button type="button" title={t('common.remove')}>{Icons.close}</button>
      </span>
    </div>
  )
}

function HomeGrid() {
  const cards = [SAMPLE, { id: 'poster-differentiated-compiler', name: t('skills.posterDesign'), custom: false }, { id: 'rednote-cover-maker', name: t('skills.socialMediaSet'), custom: false }]
  return (
    <section className="ca-landing__section" data-testid="home-grid" style={{ padding: 16, width: 720 }}>
      <div className="ca-landing__head"><h2>{t('home.startFromSkill')}</h2></div>
      <div className="ca-skillgrid">
        {cards.map((s) => (
          <button key={s.id} type="button" className="ca-skillcard">
            <span className="ca-skillcard__icon"><span className="ca-icon">{Icons.skill}</span></span>
            <span className="ca-skillcard__name">{s.name}</span>
            <span className="ca-model__tag">{s.custom ? t('home.mySkill') : t('home.builtIn')}</span>
          </button>
        ))}
      </div>
    </section>
  )
}

function ArtiSkills() {
  return (
    <div className="ca-arti__skeletons" data-testid="arti-skills" style={{ padding: 16, width: 360 }}>
      <div className="ca-arti__skel" style={{ height: 48, borderRadius: 8, background: 'var(--ca-hover)', marginBottom: 8 }} />
      <div className="ca-arti__skel" style={{ height: 48, borderRadius: 8, background: 'var(--ca-hover)', marginBottom: 8 }} />
      <div className="ca-arti__skel" style={{ height: 48, borderRadius: 8, background: 'var(--ca-hover)', marginBottom: 8 }} />
      <p className="ca-chat__hint">{t('arti.skillsEmpty')}</p>
    </div>
  )
}

const scenes: Record<string, () => any> = {
  'menu-skills': MenuSkills,
  'form-empty': SkillFormEmpty,
  'form-filled': SkillFormFilled,
  'dialog-list': () => <DialogList />,
  'dialog-list-empty': () => <DialogList empty />,
  'dialog-edit': DialogEdit,
  'slash-picker': SlashPicker,
  'skill-chip': Chip,
  'home-grid': HomeGrid,
  'arti-skills': ArtiSkills,
}

const scene = q.get('scene') || 'form-filled'
const Scene = scenes[scene] || SkillFormFilled

createRoot(document.getElementById('root')!).render(
  <div className="ca-root" style={{ minHeight: 200, padding: 16, background: 'var(--ca-page, #f5f5f5)', color: 'var(--ca-text)', width: 'fit-content' }}>
    <div id="scene"><Scene /></div>
  </div>,
)
;(globalThis as any).__ready = true
;(globalThis as any).__scenes = Object.keys(scenes)
