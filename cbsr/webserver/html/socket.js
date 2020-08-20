var socket = null;
$(function() {
	socket = new WebSocket('wss://' + window.location.hostname + ':8001');
	socket.onopen = function() {
		$(document.body).html('*');
		socket.send(getParameter('id'));
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
		if( error.message ) {
			alert(error.message);
		}
	};
});
$(window).on('unload', function() {
	socket.close();
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
	$('.vu_logo').html('<img src="img/vu_logo.jpg" '+iconStyle+'>');
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
		socket.send('tablet_answer|'+buttonValue);
	});
}
function chatBox() {
	var chatBox = $('.chatbox');
	chatBox.html('<form><input type="text"><input type="submit"></form>');
	chatBox.submit(function(e) {
		var input = $('.chatbox input').first();
		var text = input.val();
		socket.send('action_chat|'+text);
		input.val('');
		e.preventDefault();
	});
}

function getParameter(sParam) {
	var sPageURL = window.location.search.substring(1);
	var sURLVariables = sPageURL.split('&');
	for( var i = 0; i < sURLVariables.length; i++ ) {
		var sParameterName = sURLVariables[i].split('=');
		if( sParameterName[0] == sParam ) {
			return sParameterName[1];
		}
	}
}
