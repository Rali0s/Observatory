const {test}=require('node:test');
const assert=require('node:assert/strict');
const load=()=>import('./writing-editor-core.js');

test('visual edits serialize to Markdown and reopen with the same document',async()=>{
 const {editorState,serialize,parse,commands}=await load();
 let state=editorState('A quiet beginning.');
 const dispatch=tr=>{state=state.apply(tr);};
 assert.equal(commands.h2(state,dispatch),true);
 assert.match(serialize(state.doc),/^## A quiet beginning\./);
 assert.deepEqual(parse(serialize(state.doc)).toJSON(),state.doc.toJSON());
});
test('bold, italic, quotes and lists survive Markdown round trips',async()=>{
 const {parse,serialize}=await load();
 const source='# Chapter\n\n## Scene\n\n### Detail\n\n**Bold** and *italic*.\n\n- First\n- Second\n\n> A quote\n\n1. One\n2. Two';
 const doc=parse(source);
 assert.deepEqual(parse(serialize(doc)).toJSON(),doc.toJSON());
});
test('format and undo preserve writer text',async()=>{
 const {editorState,commands,serialize}=await load();
 let state=editorState('Original words.');
 const dispatch=tr=>{state=state.apply(tr);};
 commands.bullets(state,dispatch);
 assert.match(serialize(state.doc),/^\* Original words\./);
 commands.undo(state,dispatch);
 assert.equal(serialize(state.doc),'Original words.');
 commands.quote(state,dispatch);
 assert.match(serialize(state.doc),/^> Original words\./);
 commands.quote(state,dispatch);
 assert.equal(serialize(state.doc),'Original words.');
});
test('extended Markdown stays in source mode instead of being flattened',async()=>{
 const {visualSupported}=await load();
 for(const source of ['<section>Keep HTML</section>','| A | B |\n| --- | --- |\n| 1 | 2 |','[^note]: Keep footnote','- [x] Task']) assert.equal(visualSupported(source),false);
 assert.equal(visualSupported('# Normal heading\n\n**Bold** and *italic*.'),true);
});
