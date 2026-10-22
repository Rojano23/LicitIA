import axios from "axios";
export type BidStatus="READY"|"INCOMPLETE"|"REVIEW_REQUIRED"|"BLOCKED"|"NOT_APPLICABLE";
export type BidReadiness={status:BidStatus;notice:string;blocker_count:number;review_required_count:number;warning_count:number;total_issues:number;
 dimensions:{dimension:string;status:BidStatus;item_count:number;issue_count:number}[];
 issues:{id:string;dimension:string;entity_type:string;entity_id:string;status:BidStatus;severity:"BLOCKER"|"REVIEW"|"WARNING";code:string;summary:string;source_module:string;review_context:string;
 reference:{document_id:string|null;revision:number|null;page:number|null;locator:string|null;excerpt:string|null}|null}[]};
export const bidReadinessApi={read:async(base:string,tender:string)=>(await axios.get<BidReadiness>(`${base}/tenders/${tender}/bid-readiness`)).data};
