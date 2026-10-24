/** Read-only source inventory. Findings require review; matches are not proof of runtime leakage. */
import fs from 'node:fs/promises';
import path from 'node:path';
import ts from '../node_modules/typescript/lib/typescript.js';
const out=path.resolve(process.argv[2]??'backend/reports/ui_r7');await fs.mkdir(out,{recursive:true});
const roots=['frontend/src/components','frontend/src/ui'];const inventory=[];
for(const root of roots)for(const name of await fs.readdir(root)){
 if(!/\.tsx?$/.test(name)||name.includes('.test.'))continue;
 const file=path.join(root,name),text=await fs.readFile(file,'utf8');
 const ast=ts.createSourceFile(file,text,ts.ScriptTarget.Latest,true,name.endsWith('tsx')?ts.ScriptKind.TSX:ts.ScriptKind.TS);
 const strings=[];function walk(node){if(ts.isJsxText(node)&&node.text.trim())strings.push(node.text.trim().replace(/\s+/g,' '));ts.forEachChild(node,walk);}walk(ast);
 inventory.push({file,jsxText:strings,technicalCandidates:strings.filter(s=>/snapshot|stale|runtime|provider|engine|matching|\bScope\b|\bQuantity\b|artefact|LicitIA|\bTender\b/i.test(s))});
}
await fs.writeFile(path.join(out,'source-copy-inventory.json'),JSON.stringify({note:'Static JSX text only; expressions, user/source data and runtime visibility require separate review.',files:inventory.length,inventory},null,2));
console.log(JSON.stringify({files:inventory.length,textFragments:inventory.reduce((n,f)=>n+f.jsxText.length,0)}));
