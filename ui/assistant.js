'use strict';
let assistantBusy=false,wasListening=false,lastVoiceError='',voicePolling=false,updateAvailable=false;
function mood(value,label){$('jarvisStage').dataset.state=value;$('jarvisMood').textContent=label;}
async function assistantResult(result){
 const card=renderResult($('assistantConversation'),{title:'JARVIS',...result},true);
 if(result.choices)for(const choice of result.choices)card.append(actionButton(choice,()=>assistantSend(choice)));
 if(result.confirmation){const confirm=actionButton('Confirmer ce planning',async()=>{const r=await api('assistant_confirm',{token:result.confirmation});confirm.remove();await assistantResult(r);await refresh();});card.append(confirm);}
 if(result.navigate)card.append(actionButton('Ouvrir '+(names[result.navigate]||result.navigate),async()=>tab(result.navigate,result.focus)));
 if(result.handoff){handoff=result;$('handoff').classList.remove('hidden');$('assistantHandoff').classList.remove('hidden');}
 if(state.settings.voice&&!result.handoff){try{await api('speak',{text:result.text});}catch(e){message(e.message,true);}}
 card.scrollIntoView({block:'nearest',behavior:'smooth'});
}
async function assistantSend(override){
 if(assistantBusy)return;
 const query=typeof override==='string'?override:$('assistantQuery').value.trim();if(!query)return;
 assistantBusy=true;$('assistantSend').disabled=true;$('assistantMic').disabled=true;$('assistantReset').disabled=true;
 try{
  await api('voice_stop');
  const u=node('div',undefined,'message user');u.append(node('div','VOUS','who'),node('div',query,'answer'));$('assistantConversation').append(u);
  mood('thinking','Je prépare votre réponse…');
  const result=await api('assistant',{query,private:$('assistantPrivate').checked});
  $('assistantQuery').value='';await assistantResult(result);mood('idle','Prêt · microphone coupé');message('Réponse de Jarvis disponible.');
 }catch(e){mood('error','Une étape nécessite votre attention');message(e.message,true);renderResult($('assistantConversation'),{title:'JARVIS · À VÉRIFIER',text:e.message},true);}
 finally{assistantBusy=false;$('assistantSend').disabled=false;$('assistantMic').disabled=false;$('assistantReset').disabled=false;}
}
$('assistantSend').addEventListener('click',()=>assistantSend());
$('assistantQuery').addEventListener('keydown',e=>{if(e.key==='Enter'&&(e.metaKey||e.ctrlKey)){e.preventDefault();assistantSend();}});
$$('[data-assistant]').forEach(b=>b.addEventListener('click',()=>{$('assistantQuery').value=b.dataset.assistant;$('assistantQuery').focus();}));
bind('assistantReset',async()=>{await api('voice_stop');await api('assistant_reset');$('assistantConversation').replaceChildren();$('assistantQuery').value='';$('assistantPrivate').checked=false;$('assistantHandoff').classList.add('hidden');mood('idle','Nouvelle conversation · microphone coupé');});
bind('assistantStop',async()=>{await api('voice_stop');mood('idle','Voix arrêtée · microphone coupé');});
bind('assistantMic',async()=>{const s=await api('voice_state');if(s.listening){await api('voice_stop');message('Relisez la transcription puis cliquez sur Envoyer.');}else{await api('voice_listen');wasListening=true;$('assistantMic').textContent='■ Terminer la dictée';mood('listening','Je vous écoute · traitement local');message('Parlez, puis cliquez sur Terminer. Rien ne sera envoyé avant votre validation.');}});
bind('installVoice',async()=>{message((await api('voice_install')).text);},'Installation des deux voix et du modèle français · téléchargement initial…');
async function pollVoice(){if(voicePolling||!window.pywebview)return;voicePolling=true;try{const s=await api('voice_state');if(s.listening){wasListening=true;$('assistantQuery').value=s.transcript;$('assistantMic').textContent='■ Terminer la dictée';mood('listening','Je vous écoute · traitement local');}else{if(wasListening){$('assistantQuery').value=s.transcript;wasListening=false;$('assistantMic').textContent='● Parler à Jarvis';mood('idle','Transcription prête · relisez puis envoyez');}if(!assistantBusy){if(s.speaking)mood('speaking','Jarvis vous répond');else if(s.preparing)mood('thinking','Préparation de la voix locale…');else if(['speaking','thinking'].includes($('jarvisStage').dataset.state))mood('idle','Prêt · microphone coupé');}}if(s.error&&s.error!==lastVoiceError){message(s.error,true);mood('error','Vérifiez les réglages audio');}lastVoiceError=s.error;}catch(e){/* A closed native bridge has nothing to poll. */}finally{voicePolling=false;}}
async function checkUpdate(quiet=false){try{const r=await api('update_check');updateAvailable=r.available;$('updateBadge').classList.toggle('hidden',!r.available);$('installUpdate').classList.toggle('hidden',!r.available);$('updateInfo').textContent=r.available?'Version '+r.version+' disponible. '+r.notes:'Version '+r.current+' · vous êtes à jour.';if(!quiet)message(r.available?'Une mise à jour est disponible.':'Jarvis est à jour.');}catch(e){$('updateInfo').textContent='Vérification indisponible. Réessayez lorsque le Mac est connecté.';if(!quiet)message(e.message,true);}}
bind('checkUpdate',()=>checkUpdate());
bind('updateBadge',async()=>{tab('settings');$('updateInfo').scrollIntoView({block:'center'});});
bind('installUpdate',async()=>{message((await api('update_install')).text);},'Téléchargement et vérification de la mise à jour…');
window.addEventListener('pywebviewready',()=>{setInterval(pollVoice,700);checkUpdate(true);setInterval(()=>checkUpdate(true),15*60*1000);});
