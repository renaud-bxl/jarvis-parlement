ObjC.import('Cocoa');
ObjC.import('Foundation');
function run(argv) {
  const root=argv[0];
  const app=$.NSApplication.sharedApplication;
  app.setActivationPolicy($.NSApplicationActivationPolicyRegular);
  const fm=$.NSFileManager.defaultManager;
  const home=ObjC.unwrap($.NSHomeDirectory());
  const config=home+'/.config/jarvis-parlement';
  fm.createDirectoryAtPathWithIntermediateDirectoriesAttributesError($(config),true,$(),null);
  const progress=config+'/install-progress.txt';
  const log=config+'/installation-v2.log';
  const existing=fm.fileExistsAtPath($(home+'/Applications/Jarvis-Parlement/current'));
  let task=null, timer=null;
  const win=$.NSWindow.alloc.initWithContentRectStyleMaskBackingDefer($.NSMakeRect(0,0,680,450),$.NSWindowStyleMaskTitled|$.NSWindowStyleMaskClosable|$.NSWindowStyleMaskMiniaturizable,$.NSBackingStoreBuffered,false);
  win.title='JARVIS — PARLEMENT · Installation';
  win.center;
  function label(text,x,y,w,h,size) {const field=$.NSTextField.alloc.initWithFrame($.NSMakeRect(x,y,w,h));field.stringValue=$(text);field.editable=false;field.selectable=false;field.bordered=false;field.drawsBackground=false;field.font=$.NSFont.systemFontOfSize(size);win.contentView.addSubview(field);return field;}
  label('JARVIS — PARLEMENT',35,370,610,40,27);
  label(existing?'Mettre à jour ton espace parlementaire':'Installer ton espace parlementaire',35,330,610,30,18);
  label('Interface Mac • IA au choix • Courriers • Agenda • Modèles Word\nLes comptes, documents et modèles existants sont conservés.\nInternet est nécessaire. Les connexions se règlent ensuite dans Jarvis.',35,243,610,80,14);
  const option=$.NSButton.alloc.initWithFrame($.NSMakeRect(35,210,610,28));option.setButtonType($.NSSwitchButton);option.title='Installer LibreOffice si absent, pour les PDF fidèles aux modèles Word';option.state=$.NSControlStateValueOn;win.contentView.addSubview(option);
  const bar=$.NSProgressIndicator.alloc.initWithFrame($.NSMakeRect(35,165,610,18));bar.indeterminate=false;bar.minValue=0;bar.maxValue=100;win.contentView.addSubview(bar);
  const status=label('Prêt. Les dépendances et le modèle local peuvent prendre plusieurs minutes.',35,95,610,55,13);
  const start=$.NSButton.alloc.initWithFrame($.NSMakeRect(390,35,255,40));start.title=existing?'Mettre à jour et ouvrir Jarvis':'Installer et ouvrir Jarvis';start.bezelStyle=$.NSBezelStyleRounded;
  const logs=$.NSButton.alloc.initWithFrame($.NSMakeRect(35,35,200,40));logs.title='Consulter le journal';logs.bezelStyle=$.NSBezelStyleRounded;
  ObjC.registerSubclass({name:'JarvisInstallerActions',superclass:'NSObject',methods:{
    'begin:':{types:['void',['id']],implementation:function(){
      if(task&&task.running)return;
      start.enabled=false;option.enabled=false;
      fm.createFileAtPathContentsAttributes($(log),$.NSData.data,$());
      const handle=$.NSFileHandle.fileHandleForWritingAtPath($(log));
      task=$.NSTask.alloc.init;task.launchPath='/bin/bash';task.arguments=$([root+'/installer/install.sh']);
      const env=$.NSMutableDictionary.dictionaryWithDictionary($.NSProcessInfo.processInfo.environment);
      env.setObjectForKey($(progress),$('JARVIS_PROGRESS_FILE'));
      env.setObjectForKey(option.state===1?'1':'0',$('JARVIS_INSTALL_LIBREOFFICE'));
      task.environment=env;task.standardOutput=handle;task.standardError=handle;
      task.standardInput=$.NSFileHandle.fileHandleWithNullDevice;
      try{task.launch;status.stringValue='Installation en cours…';timer=$.NSTimer.scheduledTimerWithTimeIntervalTargetSelectorUserInfoRepeats(1,controller,'tick:',null,true);}catch(e){status.stringValue='Démarrage impossible : '+String(e);start.enabled=true;option.enabled=true;}
    }},
    'tick:':{types:['void',['id']],implementation:function(){
      const data=$.NSData.dataWithContentsOfFile($(progress));
      if(data){const text=ObjC.unwrap($.NSString.alloc.initWithDataEncoding(data,$.NSUTF8StringEncoding));const rows=text.split('\n');bar.doubleValue=Math.max(0,Number(rows[0]));status.stringValue=rows[1]||'Installation en cours…';}
      if(task&&!task.running){timer.invalidate;start.enabled=true;option.enabled=true;
        if(task.terminationStatus===0){status.stringValue='Installation terminée. Jarvis s’ouvre : complète le profil et les connexions.';start.title='Réinstaller / réparer';$.NSWorkspace.sharedWorkspace.openFile($(home+'/Applications/Jarvis Parlement.app'));}
        else{status.stringValue='Installation non terminée. Consulte le journal pour connaître l’étape en échec, puis relance.';start.title='Réessayer';}
      }
    }},
    'logs:':{types:['void',['id']],implementation:function(){$.NSWorkspace.sharedWorkspace.openFile($(log));}},
    'windowShouldClose:':{types:['BOOL',['id']],implementation:function(){if(task&&task.running){status.stringValue='Installation en cours. Attends sa fin avant de fermer cette fenêtre.';return false;}app.terminate(null);return true;}}
  }});
  const controller=$.JarvisInstallerActions.alloc.init;
  start.target=controller;start.action='begin:';logs.target=controller;logs.action='logs:';
  win.delegate=controller;win.contentView.addSubview(start);win.contentView.addSubview(logs);
  win.makeKeyAndOrderFront(null);app.activateIgnoringOtherApps(true);app.run;
}
