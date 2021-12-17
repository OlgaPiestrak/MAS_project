let socket = null, audioStream = null;
$(window).on('load', function() {
	const mainBody = $('#main');
	mainBody.html('Connecting to server...');
	const id = Date.now().toString(36).substring(4) + Math.random().toString(36).substring(2);
	socket = new WebSocket('wss://' + window.location.hostname + ':8001?id=' + id);
	socket.onopen = function() {
		mainBody.html('Connected! ' + id);
	};
	socket.onmessage = function(event) {
		const data = JSON.parse(event.data);
		if( data.chan == 'render_html' ) {
			mainBody.html(data.msg);
			updateListeningIcon('ListeningDone');
			vuLogo();
			englishFlag();
			activateButtons();
			chatBox();
			activateSorting();
		} else if( data.chan == 'events' ) {
			updateListeningIcon(data.msg);
		} else if( data.chan == 'text_transcript' ) {
			updateSpeechText(data.msg);
		} else if( data.chan == 'action_audio' ) {
			updateMicrophone(data.msg);
		} else if( data.chan == 'audio_language' ) {
			setTTS(data.msg);
		} else if( data.chan == 'action_say' || data.chan == 'action_say_animated' ) {
			playTTS(data.msg);
		} else if( data.chan == 'action_stop_talking' ) {
			stopTTS();
		} else {
			alert(data.chan + ': ' + data.msg);
		}
	};
	socket.onerror = function(error) {
		if( error.message ) alert(error.message);
		else alert(error);
	};
	socket.onclose = function() {
		mainBody.html('Disconnected');
		if( ttsEl ) stopTTS();
		if( audioStream ) updateMicrophone(-1);
	};
});
$(window).on('unload', function() {
	if( socket ) socket.close();
});

const iconStyle = 'style="height:10vh"';
function updateListeningIcon(input) {
	if( input.startsWith('ListeningStarted') ) {
		$('.listening_icon').html('<img src="img/listening.png" '+iconStyle+'>');
		updateSpeechText(''); // clear it
	} else if( input == 'ListeningDone' ) {
		$('.listening_icon').html('<img src="img/not_listening.png" '+iconStyle+'>');
	}
}
function updateSpeechText(input) {
	$('.speech_text').html(input);
}
function vuLogo() {
	$('.vu_logo').html('<img src="img/vu_logo.png" '+iconStyle+'>');
}
function englishFlag() {
	var englishFlag = $('.english_flag');
	englishFlag.html('<img src="img/english_flag.png" '+iconStyle+'>');
	englishFlag.click(function() {
		socket.send('audio_language|en-US');
		socket.send('dialogflow_language|en-US');
	});
}
function activateButtons() {
	$(':button').click(function() {
		const dataValue = $(this).children().data('value');
		if( dataValue ) {
			socket.send('browser_button|'+dataValue);
		} else {
			const txt = document.createElement('textarea');
			txt.innerHTML = $(this).html();
			socket.send('browser_button|'+txt.value);
		}
	});
}
function chatBox() {
	const chatBox = $('.chatbox');
	chatBox.html('<form><input id="chatbox-input" type="text" autofocus class="w-25"><input type="submit"></form>');
	const chatBoxInput = $("#chatbox-input");
	chatBoxInput.focus();

	chatBox.submit(function(e) {
		const text = chatBoxInput.val();
		socket.send('action_chat|'+text);
		chatBoxInput.val('');
		e.preventDefault();
	});
}
function activateSorting() {
	const currentSort = [];
	const sortItems = $('.sortitem');
	sortItems.click(function() {
		const $this = $(this);
		const id = $this.attr('id');
		const label = $this.find('.card-text');
		if( currentSort.length > 0 && id == currentSort[currentSort.length-1] ) {
			currentSort.pop();
			label.html('');
		} else if( label.html() == '' ) {
			currentSort.push(id);
			label.html(currentSort.length)
		}
	});
	sortItems.parent().parent().after('<form class="mt-3"><input type="submit" value="Klaar!"></form>');
	$('form').submit(function(e) {
		socket.send('browser_button|'+JSON.stringify(currentSort));
		currentSort = [];
		e.preventDefault();
	});
}
let ttsEl = null, ttsUrl = null, langSet = false;
function setTTS(lang) {	
	ttsUrl = '//translate.google.com/translate_tts?ie=UTF-8&client=tw-ob&tl='+lang+'&q=';
	langSet = true;
}
function playTTS(text) {
	if( !$('.audioEnabled').length || !ttsUrl ) return;
	if( langSet ) {
		socket.send('events|LanguageChanged');
		langSet = false;
	}
	
	if( ttsEl ) stopTTS();
	if( text ) {
		ttsEl = $('<audio></audio>');
		ttsEl.attr('src', ttsUrl+text);
		ttsEl.appendTo('body');
		ttsEl.on('ended', function(){socket.send('events|TextDone')});
   		ttsEl[0].play();
	}
	socket.send('events|TextStarted');
	if( !text ) socket.send('events|TextDone');
}
function stopTTS() {
	if( ttsEl ) {
		ttsEl.remove();
		ttsEl = null;
		socket.send('events|TextDone');
	}
}
function updateMicrophone(input) {	
	if( input >= 0 ) {
		if( !$('.audioEnabled').length ) return;
		if( audioStream ) updateMicrophone(-1);
		audioStream = true;
		navigator.getUserMedia = navigator.getUserMedia || navigator.webkitGetUserMedia || navigator.mozGetUserMedia || navigator.msGetUserMedia; 
		navigator.getUserMedia({audio: true}, function(stream) {
			audioStream = stream;
	    	const context = window.AudioContext || window.webkitAudioContext;
			const audioContext = new context();
			const sampleRate = audioContext.sampleRate;
			const volume = audioContext.createGain();
			const audioInput = audioContext.createMediaStreamSource(audioStream);
			audioInput.connect(volume);
			const processor = audioContext.createScriptProcessor || audioContext.createJavaScriptNode; 
			const recorder = processor.call(audioContext, 2048, 1, 1);
			recorder.onaudioprocess = function(event) {
	   			const PCM32fSamples = event.inputBuffer.getChannelData(0);
				const PCM16iSamples = new ArrayBuffer(PCM32fSamples.length*2);
				const dataView = new DataView(PCM16iSamples);
				for (let i = 0; i < PCM32fSamples.length; i++) {
	   				let val = Math.floor(32767 * PCM32fSamples[i]);
	   				val = Math.min(32767, val);
	   				val = Math.max(-32768, val);
	   				dataView.setInt16(i*2, val, true);
				}
				socket.send(PCM16iSamples);
				if( !audioStream ) recorder.disconnect(); 
			};
			volume.connect(recorder);
			recorder.connect(audioContext.destination);
			socket.send('events|ListeningStarted;1;'+sampleRate);
			if( input > 0 ) setTimeout(function(){updateMicrophone(-1)}, input*1000);
	   }, function(error){
	       alert('Error capturing audio.');
	   });
	} else if( input < 0 && audioStream ) {
		audioStream.getTracks().forEach(track => track.stop());
		audioStream = null;
		socket.send('events|ListeningDone');
	}
}