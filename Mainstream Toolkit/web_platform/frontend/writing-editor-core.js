import {schema, defaultMarkdownParser, defaultMarkdownSerializer} from 'prosemirror-markdown';
import {EditorState} from 'prosemirror-state';
import {baseKeymap, setBlockType, toggleMark, wrapIn, lift} from 'prosemirror-commands';
import {wrapInList, liftListItem} from 'prosemirror-schema-list';
import {history, undo, redo} from 'prosemirror-history';
import {keymap} from 'prosemirror-keymap';
import {inputRules, wrappingInputRule, textblockTypeInputRule} from 'prosemirror-inputrules';
import {buildKeymap} from 'prosemirror-example-setup';

export {schema, undo, redo};
export const parse = text => defaultMarkdownParser.parse(text);
export const serialize = doc => defaultMarkdownSerializer.serialize(doc);
// Keep extended Markdown in source mode instead of silently flattening its structure.
export function visualSupported(text) {
  return !/(^|\n)\s*\|?.+\|.+\n\s*\|?\s*:?-{3,}|(^|\n)\s*\[\^[^\]]+\]:|<\/?[a-z][^>]*>|(^|\n)\s*[-*+] \[[ xX]\]/m.test(text);
}
export function editorState(text) {
  return EditorState.create({schema, doc:parse(text), plugins:[
    inputRules({rules:[
      textblockTypeInputRule(/^(#{1,6})\s$/, schema.nodes.heading, match=>({level:match[1].length})),
      wrappingInputRule(/^\s*>\s$/,schema.nodes.blockquote),
      wrappingInputRule(/^\s*([-+*])\s$/,schema.nodes.bullet_list),
      wrappingInputRule(/^(\d+)\.\s$/,schema.nodes.ordered_list,match=>({order:+match[1]}),
        (match,node)=>node.childCount+node.attrs.order===+match[1]),
      textblockTypeInputRule(/^```$/,schema.nodes.code_block),
    ]}),
    keymap(buildKeymap(schema)),keymap(baseKeymap),history(),
  ]});
}
function inNode(state,type) {
  const {$from}=state.selection;
  for(let depth=$from.depth;depth>0;depth--) if($from.node(depth).type===type) return true;
  return false;
}
function list(type) {
  return (state,dispatch)=>inNode(state,type)
    ? liftListItem(schema.nodes.list_item)(state,dispatch)
    : wrapInList(type)(state,dispatch);
}
export const commands = {
  paragraph:setBlockType(schema.nodes.paragraph),
  h1:setBlockType(schema.nodes.heading,{level:1}), h2:setBlockType(schema.nodes.heading,{level:2}),
  h3:setBlockType(schema.nodes.heading,{level:3}), bold:toggleMark(schema.marks.strong),
  italic:toggleMark(schema.marks.em), bullets:list(schema.nodes.bullet_list),
  numbers:list(schema.nodes.ordered_list),
  quote:(state,dispatch)=>inNode(state,schema.nodes.blockquote)?lift(state,dispatch):wrapIn(schema.nodes.blockquote)(state,dispatch),
  undo,redo,
};
export function active(state,name) {
  if(name==='bold'||name==='italic') {
    const mark=schema.marks[name==='bold'?'strong':'em'];
    const {from,to,empty,$from}=state.selection;
    return empty?!!mark.isInSet(state.storedMarks||$from.marks()):state.doc.rangeHasMark(from,to,mark);
  }
  if(/^h[1-3]$/.test(name)) return state.selection.$from.parent.type===schema.nodes.heading&&state.selection.$from.parent.attrs.level===+name[1];
  return inNode(state,schema.nodes[{bullets:'bullet_list',numbers:'ordered_list',quote:'blockquote',paragraph:'paragraph'}[name]]);
}
