export const companyEvidenceTypes:Readonly<Record<string,string>>={CORPORATE_EXISTENCE:'Existencia legal',LEGAL_AUTHORITY:'Facultades / poder',TAX_REGISTRATION:'Registro fiscal',TAX_COMPLIANCE:'Cumplimiento fiscal',SOCIAL_SECURITY_COMPLIANCE:'Seguridad social',REGISTRATION:'Registro',CERTIFICATION:'Certificación',PERSONNEL_QUALIFICATION:'Acreditación de personal',EXPERIENCE:'Experiencia',SAFETY_CREDENTIAL:'Seguridad',GUARANTEE:'Garantía',COMMERCIAL_DOCUMENT:'Documento comercial',OTHER:'Otros',UNKNOWN:'Sin clasificar'};
export const evidenceReview=(value?:string)=>({APPROVED:'Validada por una persona',PENDING:'Pendiente',NEEDS_REVIEW:'Requiere revisión',REJECTED:'Descartada como evidencia'}[value??'PENDING']??'Revisar estado');
export const localDate=()=>{const now=new Date();return `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`;};
export function registeredValidity(expiration:string|null,today=localDate()){
 if(!expiration)return 'Sin fecha de vigencia';
 const parsed=new Date(expiration+'T12:00:00Z');
 if(!/^\d{4}-\d{2}-\d{2}$/.test(expiration)||Number.isNaN(parsed.getTime())||parsed.toISOString().slice(0,10)!==expiration)return 'Fecha por revisar';
 return expiration<today?`Fecha registrada vencida: ${expiration}`:`Vigencia registrada hasta ${expiration}`;
}
