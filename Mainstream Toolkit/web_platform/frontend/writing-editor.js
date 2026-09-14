import {EditorView} from 'prosemirror-view';
import {editorState, commands, active, serialize, visualSupported} from './writing-editor-core.js';
import 'prosemirror-view/style/prosemirror.css';
import './writing-editor.css';

function element(tag,props={},text='') {
  const el=document.createElement(tag);
  for(const [key,value] of Object.entries(props)) el.setAttribute(key,value);
  el.textContent=text;
  return el;
}
export function enhance(textarea) {
  if(textarea.dataset.editorReady) return;
  const root=element('section',{class:'writing-editor','aria-label':'Writing editor'});
  const modes=element('div',{class:'editor-modes',role:'group','aria-label':'Editor mode'});
  const visual=element('button',{type:'button','aria-pressed':'false'},'Visual');
  const markdown=element('button',{type:'button','aria-pressed':'true'},'Markdown');
  const help=element('button',{type:'button','aria-expanded':'false'},'Markdown help');
  const guide=element('div',{class:'editor-guide',id:textarea.id+'-guide',hidden:'','role':'region','aria-label':'Markdown help guide'});
  help.setAttribute('aria-controls',guide.id);
  guide.append(element('h3',{},'A quick Markdown guide'),element('p',{},'In Visual mode, select text and use the toolbar. In Markdown mode, use these simple patterns.'));
  const examples=[['Heading 1','# Heading'],['Heading 2','## Heading'],['Heading 3','### Heading'],['Bold','**bold words**'],['Italic','*italic words*'],['Bullets','- First item\n- Second item'],['Numbered list','1. First item\n2. Second item'],['Quote','> Quoted words'],['New paragraph','Leave a blank line between paragraphs.']];
  const table=element('table');
  for(const [name,source] of examples) {const row=element('tr');row.append(element('th',{scope:'row'},name));const cell=element('td');cell.append(element('code',{},source));row.append(cell);table.append(row);}
  guide.append(table,element('p',{},'Shortcuts: Ctrl/⌘ B for bold, Ctrl/⌘ I for italic, Ctrl/⌘ Z to undo. In Visual mode, typing #, ##, ###, -, 1. or > followed by a space converts the current line. Formatting changes are saved when you use the page’s Save or Preview button.'));
  const toolbar=element('div',{class:'editor-toolbar',role:'group','aria-label':'Text formatting',hidden:''});
  const mount=element('div',{class:'editor-visual',hidden:''});
  const status=element('p',{class:'editor-status',id:textarea.id+'-editor-status',role:'status','aria-live':'polite'});
  modes.append(visual,markdown,help);
  textarea.before(root);
  root.append(modes,guide,toolbar,mount,textarea,status);
  const originalRequired=textarea.required;
  const originalLabel=Array.from(document.querySelectorAll('label')).find(label=>label.htmlFor===textarea.id);
  const label=originalLabel?.textContent.replace(/:$/,'') || textarea.name;
  let view=null,mode='markdown',lastSource=null;
  const buttons=[];
  function sync() {
    if(view&&mode==='visual') {
      textarea.value=serialize(view.state.doc);
      textarea.dispatchEvent(new Event('input',{bubbles:true}));
    }
  }
  function toolbarState() {
    for(const [name,button] of buttons) {
      button.disabled=!commands[name](view.state);
      if(name!=='undo'&&name!=='redo') button.setAttribute('aria-pressed',String(active(view.state,name)));
    }
  }
  function createView() {
    return new EditorView(mount,{
      state:editorState(textarea.value),
      attributes:{role:'textbox','aria-multiline':'true','aria-label':label+' visual editor','aria-describedby':status.id},
      dispatchTransaction(transaction) {
        this.updateState(this.state.apply(transaction));
        if(transaction.docChanged) sync();
        toolbarState();
      },
      // Referenced artwork remains in the source without loading remote images while writing.
      nodeViews:{image(node){return {dom:element('span',{class:'editor-image-reference'},node.attrs.alt?'Image: '+node.attrs.alt:'Image reference')};}},
      handleClick(view,pos,event){return !!event.target.closest('a');},
    });
  }
  function switchMode(next,focus=true) {
    if(next==='visual'&&mode==='visual'&&view) {if(focus) view.focus();return;}
    if(next==='visual') {
      if(!visualSupported(textarea.value)) {
        status.textContent='This draft uses HTML, tables, checklists, or footnotes. Keep editing it in Markdown to preserve that formatting.';
        return;
      }
      try {
        if(!view) view=createView();
        else if(lastSource!==textarea.value) view.updateState(editorState(textarea.value));
      } catch {
        status.textContent='This draft could not be opened visually. Your Markdown is unchanged and remains editable.';
        return;
      }
    } else if(mode==='visual') {
      // Transactions already synchronize the source; a mode switch alone changes no text.
      lastSource=textarea.value;
    }
    mode=next;
    const rich=mode==='visual';
    textarea.hidden=rich;textarea.required=rich?false:originalRequired;
    mount.hidden=!rich;toolbar.hidden=!rich;
    visual.setAttribute('aria-pressed',String(rich));markdown.setAttribute('aria-pressed',String(!rich));
    status.textContent=rich?'Format as you write. Your work is stored as Markdown.':'Edit Markdown directly, or switch to Visual for formatting controls.';
    if(rich) toolbarState();
    try {localStorage.setItem('observatory-editor-mode',mode);} catch {}
    if(focus) {if(rich) view.focus();else textarea.focus();}
  }
  for(const [name,text,title] of [['paragraph','¶','Paragraph'],['h1','H1','Heading 1'],['h2','H2','Heading 2'],['h3','H3','Heading 3'],['bold','B','Bold'],['italic','I','Italic'],['bullets','• List','Bulleted list'],['numbers','1. List','Numbered list'],['quote','❝','Block quote'],['undo','↶','Undo'],['redo','↷','Redo']]) {
    const button=element('button',{type:'button',title,'aria-label':title,'data-format':name},text);
    button.addEventListener('mousedown',event=>event.preventDefault());
    button.addEventListener('click',()=>{commands[name](view.state,view.dispatch,view);view.focus();toolbarState();});
    toolbar.append(button);buttons.push([name,button]);
  }
  help.addEventListener('click',()=>{guide.hidden=!guide.hidden;help.setAttribute('aria-expanded',String(!guide.hidden));});
  visual.addEventListener('click',()=>switchMode('visual'));
  markdown.addEventListener('click',()=>switchMode('markdown'));
  originalLabel?.addEventListener('click',event=>{if(mode==='visual'){event.preventDefault();view.focus();}});
  textarea.form?.addEventListener('submit',event=>{
    if(mode!=='visual') return;
    // Preserve the existing source if the visual document has not been edited.
    const empty=!textarea.value.trim();
    if((originalRequired&&empty)||(textarea.maxLength>0&&textarea.value.length>textarea.maxLength)) {
      event.preventDefault();
      status.textContent=empty?'Add some writing before continuing.':`This field supports up to ${textarea.maxLength.toLocaleString()} characters.`;
      view.focus();
    }
  });
  textarea.dataset.editorReady='true';
  let initial='visual';
  try {initial=localStorage.getItem('observatory-editor-mode')||'visual';} catch {}
  switchMode(initial==='markdown'?'markdown':'visual',false);
}
const desktopViewport=window.matchMedia('(min-width: 768px)');
function startEditors() {
  if(!desktopViewport.matches) return;
  for(const textarea of document.querySelectorAll('textarea[data-writing-editor]')) {
    try {enhance(textarea);} catch {textarea.hidden=false;}
  }
}
startEditors();
desktopViewport.addEventListener('change',startEditors);
