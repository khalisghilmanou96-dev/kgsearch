<?php
declare(strict_types=1);
ini_set('display_errors','0');
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');
function respond(int $status,array $data): never {http_response_code($status);echo json_encode($data,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES|JSON_INVALID_UTF8_SUBSTITUTE);exit;}
function fetchJson(string $url,array $headers=[]): array {
 if(!function_exists('curl_init'))respond(503,['error'=>'Extension PHP cURL requise.']);
 $ch=curl_init($url);
 curl_setopt_array($ch,[CURLOPT_RETURNTRANSFER=>true,CURLOPT_TIMEOUT=>16,CURLOPT_CONNECTTIMEOUT=>6,CURLOPT_FOLLOWLOCATION=>false,CURLOPT_HTTPHEADER=>array_merge(['Accept: application/json','User-Agent: KSEARCH/1.1 (https://kgstudio.fr/search/; contact: contact@kgstudio.fr)'],$headers)]);
 $body=curl_exec($ch);$status=(int)curl_getinfo($ch,CURLINFO_HTTP_CODE);$curlError=curl_error($ch);
 if($body===false||$status<200||$status>=300)respond(502,['error'=>'Source temporairement indisponible (HTTP '.($status?:'réseau').').','details'=>$curlError?:null]);
 $json=json_decode($body,true);
 if(!is_array($json))respond(502,['error'=>'Réponse invalide du fournisseur.']);
 return $json;
}
if(($_SERVER['REQUEST_METHOD']??'GET')!=='GET')respond(405,['error'=>'Méthode non autorisée.']);
$countries=json_decode((string)file_get_contents(__DIR__.'/countries.json'),true);
$code=strtoupper(trim((string)($_GET['country']??'')));
$selected=null;foreach($countries as $c){if($c['code']===$code){$selected=$c;break;}}
if(!$selected)respond(400,['error'=>'Pays inconnu.']);
$q=trim((string)($_GET['q']??''));
if($q===''||strlen($q)>600||(function_exists('mb_strlen')?mb_strlen($q):strlen($q))>180)respond(400,['error'=>'Recherche vide ou trop longue.']);
$page=filter_var($_GET['page']??1,FILTER_VALIDATE_INT,['options'=>['min_range'=>1,'max_range'=>10]]);
if($page===false)respond(400,['error'=>'Page invalide.']);
$source='hybrid';
$tld=strtolower((string)$selected['tld']);
$results=[];$hasMore=false;$seen=[];
$add=function(array $item)use(&$results,&$seen,$tld):void{
 $url=(string)($item['url']??'');$parts=parse_url($url);
 if(!is_array($parts)||!in_array(strtolower($parts['scheme']??''),['http','https'],true))return;
 $host=strtolower(rtrim((string)($parts['host']??''),'.'));
 if(!str_ends_with($host,'.'.$tld)||isset($seen[$url]))return;
 $seen[$url]=true;$results[]=$item;
};
$db=__DIR__.'/data/index.sqlite';
if(is_file($db)&&extension_loaded('pdo_sqlite')){
 try{
  $pdo=new PDO('sqlite:'.$db,null,null,[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION]);
  $tokens=preg_split('/\s+/u',mb_strtolower($q,'UTF-8'));
  $tokens=array_slice(array_values(array_filter($tokens,fn($x)=>mb_strlen($x)>=2)),0,8);
  if($tokens){
   $where=[];$params=[':tld'=>$tld];
   foreach($tokens as $i=>$token){$k=':term'.$i;$where[]='(title LIKE '.$k.' OR description LIKE '.$k.' OR content LIKE '.$k.')';$params[$k]='%'.str_replace(['%','_','\\'],['\%','\_','\\'], $token).'%';}
   $sql='SELECT url,title,description FROM pages WHERE tld=:tld AND '.implode(' AND ',$where).' ORDER BY crawled_at DESC LIMIT 100';
   $stmt=$pdo->prepare($sql);$stmt->execute($params);
   foreach($stmt as $row)$add(['url'=>$row['url'],'title'=>$row['title'],'description'=>$row['description'],'source'=>'KSEARCHBOT']);
  }
 }catch(Throwable $e){error_log('KSEARCHBOT index: '.$e->getMessage());}
}
$key=getenv('BRAVE_API_KEY')?:'';
if($key===''&&is_file(__DIR__.'/config.php')){$settings=require __DIR__.'/config.php';$key=(string)($settings['BRAVE_API_KEY']??'');}
$externalAvailable=$key!==''&&$key!=='VOTRE_CLE_API_BRAVE';
$externalMore=false;
if($externalAvailable){
 $url='https://api.search.brave.com/res/v1/web/search?'.http_build_query(['q'=>$q.' site:.'.$tld,'count'=>20,'offset'=>($page-1)*20,'safesearch'=>'moderate'],'','&',PHP_QUERY_RFC3986);
 if(function_exists('curl_init')){
  $ch=curl_init($url);curl_setopt_array($ch,[CURLOPT_RETURNTRANSFER=>true,CURLOPT_TIMEOUT=>12,CURLOPT_CONNECTTIMEOUT=>5,CURLOPT_FOLLOWLOCATION=>false,CURLOPT_HTTPHEADER=>['Accept: application/json','X-Subscription-Token: '.$key]]);
  $body=curl_exec($ch);$status=(int)curl_getinfo($ch,CURLINFO_HTTP_CODE);curl_close($ch);
  if($body!==false&&$status===200){$data=json_decode($body,true);if(is_array($data)){
   foreach(($data['web']['results']??[]) as $item)$add(['url'=>(string)($item['url']??''),'title'=>strip_tags((string)($item['title']??'')),'description'=>strip_tags((string)($item['description']??'')),'source'=>'Brave Search']);
   $externalMore=!empty($data['query']['more_results_available']);
  }}
 }
}
// Index local disponible sur les premières pages; dédoublonnage des deux sources.
$hasMore=$externalAvailable&&$externalMore&&$page<10;
respond(200,['country'=>$selected,'query'=>$q,'page'=>$page,'source'=>$source,'results'=>$results,'hasMore'=>$hasMore,'notice'=>$externalAvailable?'Index local + recherche Brave, domaines .'.$tld.' uniquement.':'Index local uniquement : configurez BRAVE_API_KEY pour activer les résultats externes.']);
