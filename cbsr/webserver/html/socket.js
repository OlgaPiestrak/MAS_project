$(function() {
	var socket = new SockJS('https://' + window.location.hostname + ':8001');
	socket.onopen = function() {
		$(document.body).html('*');
	};
	socket.onmessage = function(event) {
		var data = JSON.parse(event.data);
		if( data.chan == 'render_html' ) {
			$(document.body).html(data.msg);
			updateListeningIcon('ListeningDone');
			vuLogo();
			englishFlag();
			activateButtons();
			chatBox();
		} else if( data.chan == 'events' ) {
			updateListeningIcon(data.msg);
		} else if( data.chan == 'text_transcript' ) {
			updateSpeechText(data.msg);
		} else {
			alert(data.chan + ': ' + data.msg);
		}
	};
	socket.onerror = function(error) {
		if( error.message ) alert(error.message);
	};
	socket.onclose = function() {
		$(document.body).html('');
	};
});

var iconStyle = 'style="height:10vh"';
function updateListeningIcon(input) {
	if( input == 'ListeningStarted' ) {
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
		var buttonValue = $(this).html();
		socket.send('browser_button|'+buttonValue);
	});
}
function chatBox() {
	var chatBox = $('.chatbox');
	chatBox.html('<form><input type="text" autofocus class="w-25"><input type="submit"></form>');
	chatBox.submit(function(e) {
		var input = $('.chatbox input').first();
		var text = input.val();
		socket.send('action_chat|'+text);
		input.val('');
		e.preventDefault();
	});
}