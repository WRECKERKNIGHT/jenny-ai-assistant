// FRIDAY - Personal Assistant Client Application (Upgraded ChatGPT/Gemini Conversational Agent)

// Web Audio API Synthesizer (Zero-dependency sound effects with zero latency buffer)
const audioCtx = new (window.AudioContext || window.webkitAudioContext)({ latencyHint: 'interactive' });

function playBeep(freq, duration, type = 'sine') {
  try {
    if (audioCtx.state === 'suspended') {
      audioCtx.resume();
    }
    const osc = audioCtx.createOscillator();
    const gainNode = audioCtx.createGain();
    
    osc.type = type;
    osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
    
    gainNode.gain.setValueAtTime(0.08, audioCtx.currentTime);
    gainNode.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + duration);
    
    osc.connect(gainNode);
    gainNode.connect(audioCtx.destination);
    
    osc.start();
    osc.stop(audioCtx.currentTime + duration);
  } catch (e) {
    console.error('Audio synthesizer error:', e);
  }
}

function playBootChime() {
  try {
    if (audioCtx.state === 'suspended') {
      audioCtx.resume();
    }
    const now = audioCtx.currentTime;
    
    // Rich cinematic ambient pad chord progression (C Major -> E Minor - 4.5 seconds duration)
    const padNotes = [130.81, 164.81, 196.00, 261.63, 329.63]; // C3, E3, G3, C4, E4
    padNotes.forEach((freq, idx) => {
      const osc = audioCtx.createOscillator();
      const gainNode = audioCtx.createGain();
      
      osc.type = 'sine';
      osc.frequency.setValueAtTime(freq, now);
      
      // Slow fade-in and long cinematic fade-out
      gainNode.gain.setValueAtTime(0, now);
      gainNode.gain.linearRampToValueAtTime(0.04, now + 1.2);
      gainNode.gain.exponentialRampToValueAtTime(0.001, now + 4.5);
      
      osc.connect(gainNode);
      gainNode.connect(audioCtx.destination);
      
      osc.start(now);
      osc.stop(now + 4.5);
    });

    // Elegant rising space-themed arpeggio overlay
    const arpeggioNotes = [261.63, 329.63, 392.00, 523.25, 659.25, 783.99, 1046.50]; // C4, E4, G4, C5, E5, G5, C6
    arpeggioNotes.forEach((freq, idx) => {
      const osc = audioCtx.createOscillator();
      const gainNode = audioCtx.createGain();
      
      osc.type = 'sine';
      osc.frequency.setValueAtTime(freq, now + idx * 0.18);
      
      gainNode.gain.setValueAtTime(0, now + idx * 0.18);
      gainNode.gain.linearRampToValueAtTime(0.05, now + idx * 0.18 + 0.05);
      gainNode.gain.exponentialRampToValueAtTime(0.001, now + idx * 0.18 + 0.8);
      
      osc.connect(gainNode);
      gainNode.connect(audioCtx.destination);
      
      osc.start(now + idx * 0.18);
      osc.stop(now + idx * 0.18 + 0.8);
    });

    // Deep resonant sci-fi sweep
    const filter = audioCtx.createBiquadFilter();
    filter.type = 'lowpass';
    filter.Q.setValueAtTime(5, now);
    filter.frequency.setValueAtTime(100, now);
    filter.frequency.exponentialRampToValueAtTime(1600, now + 3.0);
    
    const sweepOsc = audioCtx.createOscillator();
    sweepOsc.type = 'sawtooth';
    sweepOsc.frequency.setValueAtTime(65.41, now); // C2
    sweepOsc.frequency.linearRampToValueAtTime(110.00, now + 3.0); // A2
    
    const sweepGain = audioCtx.createGain();
    sweepGain.gain.setValueAtTime(0.02, now);
    sweepGain.gain.exponentialRampToValueAtTime(0.001, now + 4.0);
    
    sweepOsc.connect(filter);
    filter.connect(sweepGain);
    sweepGain.connect(audioCtx.destination);
    
    sweepOsc.start(now);
    sweepOsc.stop(now + 4.0);
  } catch (e) {
    console.error('Audio start-up boot chime error:', e);
  }
}

function playIntroMusic() {
  try {
    if (audioCtx.state === 'suspended') {
      audioCtx.resume();
    }
    const now = audioCtx.currentTime;
    
    // Punchy 2-chord progression (1.8s total duration)
    const chords = [
      [130.81, 164.81, 196.00, 293.66, 329.63], // Cmaj9
      [174.61, 220.00, 261.63, 349.23, 392.00]  // Fmaj9
    ];

    chords.forEach((chord, chordIdx) => {
      const startTime = now + chordIdx * 0.95;
      const duration = 1.1;
      
      chord.forEach((freq, idx) => {
        const osc = audioCtx.createOscillator();
        const gainNode = audioCtx.createGain();
        const filter = audioCtx.createBiquadFilter();
        
        osc.type = 'sine';
        osc.frequency.setValueAtTime(freq, startTime);
        
        filter.type = 'lowpass';
        filter.frequency.setValueAtTime(450, startTime);
        filter.frequency.exponentialRampToValueAtTime(1200, startTime + duration * 0.4);
        filter.frequency.exponentialRampToValueAtTime(300, startTime + duration);
        
        gainNode.gain.setValueAtTime(0, startTime);
        gainNode.gain.linearRampToValueAtTime(0.05, startTime + 0.3);
        gainNode.gain.linearRampToValueAtTime(0.05, startTime + duration - 0.3);
        gainNode.gain.exponentialRampToValueAtTime(0.001, startTime + duration);
        
        osc.connect(filter);
        filter.connect(gainNode);
        gainNode.connect(audioCtx.destination);
        
        osc.start(startTime);
        osc.stop(startTime + duration);
      });
    });

    // Sub-bass root notes for power
    const bassNotes = [65.41, 87.31]; // C2, F2
    bassNotes.forEach((freq, chordIdx) => {
      const startTime = now + chordIdx * 0.95;
      const duration = 1.1;
      
      const osc = audioCtx.createOscillator();
      const gainNode = audioCtx.createGain();
      
      osc.type = 'triangle';
      osc.frequency.setValueAtTime(freq, startTime);
      
      gainNode.gain.setValueAtTime(0, startTime);
      gainNode.gain.linearRampToValueAtTime(0.06, startTime + 0.2);
      gainNode.gain.exponentialRampToValueAtTime(0.001, startTime + duration);
      
      osc.connect(gainNode);
      gainNode.connect(audioCtx.destination);
      
      osc.start(startTime);
      osc.stop(startTime + duration);
    });
  } catch (e) {
    console.error('Audio start-up boot chime error:', e);
  }
}

const sfx = {
  hover: () => playBeep(800, 0.05, 'triangle'),
  click: () => playBeep(1200, 0.08, 'sine'),
  confirm: () => {
    playBeep(600, 0.08, 'sine');
    setTimeout(() => playBeep(900, 0.12, 'sine'), 80);
  },
  error: () => {
    playBeep(220, 0.15, 'sawtooth');
    setTimeout(() => playBeep(180, 0.2, 'sawtooth'), 100);
  },
  alert: () => {
    playBeep(880, 0.1, 'square');
    setTimeout(() => playBeep(880, 0.1, 'square'), 150);
    setTimeout(() => playBeep(880, 0.1, 'square'), 300);
  },
  boot: () => playBootChime()
};

// State Variables
let canvas;
let ctx;
let recognition;
let isVoiceMuted = false;
let isSpeaking = false;
let isListening = false;
let isPassiveWakeWordActive = true;
let receivedSpeechThisSession = false;
let systemUptimeSeconds = 0;
let permanentAnalyser = null;
let speechSessionId = 0;

// Mic Visualizer state
let micStream = null;
let micSource = null;
let micAnalyser = null;
let listeningWaveformFrameId;

// Speech Synthesis Setup
let selectedVoice = null;
const synth = window.speechSynthesis;
const voiceSelect = document.getElementById('voice-select');

// Filtered Female Voice Selection: US, UK, India (ElevenLabs & Web Speech)
function populateVoiceList() {
  if (typeof speechSynthesis === 'undefined' || !voiceSelect) return;
  
  const voices = synth.getVoices();
  voiceSelect.innerHTML = '';

  // 1. ElevenLabs Natural Female Voices Group
  const elevenGroup = document.createElement('optgroup');
  elevenGroup.label = '✨ ELEVENLABS NATURAL FEMALE VOICES';

  const elevenFemaleVoices = [
    { name: 'Tia Mirza (ElevenLabs - OUBnvvuqEKdDWtapoJFn)', id: 'OUBnvvuqEKdDWtapoJFn' },
    { name: 'Rachel - Natural American (ElevenLabs - 21m00Tcm4TlvDq8ikWAM)', id: '21m00Tcm4TlvDq8ikWAM' },
    { name: 'Domi - Energetic Female (ElevenLabs - AZnzlk1XvdvUeBnXmlld)', id: 'AZnzlk1XvdvUeBnXmlld' },
    { name: 'Bella - Soft Conversational (ElevenLabs - EXAVITQu4vr4xnSDxMaL)', id: 'EXAVITQu4vr4xnSDxMaL' },
    { name: 'Elli - Calm Female (ElevenLabs - MF3mGyEYCl7XYWbV9V6O)', id: 'MF3mGyEYCl7XYWbV9V6O' }
  ];

  elevenFemaleVoices.forEach(v => {
    const opt = document.createElement('option');
    opt.textContent = v.name;
    opt.value = v.id;
    opt.setAttribute('data-elevenlabs-id', v.id);
    elevenGroup.appendChild(opt);
  });
  voiceSelect.appendChild(elevenGroup);
  
  // List of high-quality female voice names
  const femaleVoiceKeywords = [
    'samantha', 'victoria', 'veena', 'siri', 'zira', 'aria', 'jenny',
    'kate', 'serena', 'karen', 'neerja', 'kalpana', 'swara', 'hazel',
    'fiona', 'moira', 'tessa', 'google us english', 'google uk english female', 'google हिंदी'
  ];

  // Filter allowed voices strictly for US, UK, India (English/Hindi)
  const allowedVoices = voices.filter(v => {
    const lang = (v.lang || '').toLowerCase();
    const name = (v.name || '').toLowerCase();
    
    if (name.includes('compact')) return false;

    return lang.startsWith('en-us') || lang.startsWith('en_us') ||
           lang.startsWith('en-gb') || lang.startsWith('en_gb') ||
           lang.startsWith('en-in') || lang.startsWith('en_in') ||
           lang.startsWith('hi') || lang.includes('hindi') || lang.includes('india');
  });

  // Sort female voices first
  allowedVoices.sort((a, b) => {
    const aName = a.name.toLowerCase();
    const bName = b.name.toLowerCase();
    
    const aIsFemale = femaleVoiceKeywords.some(kw => aName.includes(kw));
    const bIsFemale = femaleVoiceKeywords.some(kw => bName.includes(kw));
    
    if (aIsFemale && !bIsFemale) return -1;
    if (!aIsFemale && bIsFemale) return 1;
    return aName.localeCompare(bName);
  });

  // Categorize into Optgroups
  const indiaGroup = document.createElement('optgroup');
  indiaGroup.label = '🇮🇳 INDIA (Female & Natural English/Hindi)';

  const usGroup = document.createElement('optgroup');
  usGroup.label = '🇺🇸 UNITED STATES (Female & Natural English)';

  const ukGroup = document.createElement('optgroup');
  ukGroup.label = '🇬🇧 UNITED KINGDOM (Female & Natural English)';

  const savedVoiceName = localStorage.getItem('friday_preferred_voice');
  let matchedSaved = false;

  allowedVoices.forEach(voice => {
    const lang = (voice.lang || '').toLowerCase();
    const name = (voice.name || '').toLowerCase();
    
    const option = document.createElement('option');
    option.textContent = `👩 ${voice.name} (${voice.lang})`;
    option.setAttribute('data-name', voice.name);
    option.value = voice.name;

    if (savedVoiceName && voice.name === savedVoiceName) {
      option.selected = true;
      selectedVoice = voice;
      matchedSaved = true;
    }

    if (lang.includes('in') || name.includes('india') || name.includes('hindi') || name.includes('veena') || name.includes('rishi')) {
      indiaGroup.appendChild(option);
    } else if (lang.includes('gb') || name.includes('uk')) {
      ukGroup.appendChild(option);
    } else {
      usGroup.appendChild(option);
    }
  });

  if (indiaGroup.children.length > 0) voiceSelect.appendChild(indiaGroup);
  if (usGroup.children.length > 0) voiceSelect.appendChild(usGroup);
  if (ukGroup.children.length > 0) voiceSelect.appendChild(ukGroup);

  if (!matchedSaved && allowedVoices.length > 0) {
    selectedVoice = allowedVoices[0];
    localStorage.setItem('friday_preferred_voice', selectedVoice.name);
  }
}

populateVoiceList();
if (speechSynthesis.onvoiceschanged !== undefined) {
  speechSynthesis.onvoiceschanged = populateVoiceList;
}

if (voiceSelect) {
  voiceSelect.addEventListener('change', () => {
    const selectedOption = voiceSelect.selectedOptions[0];
    if (!selectedOption) return;
    const name = selectedOption.getAttribute('data-name');
    const voices = synth.getVoices();
    const found = voices.find(v => v.name === name);
    if (found) {
      selectedVoice = found;
      localStorage.setItem('friday_preferred_voice', name);
      sfx.click();
      speak(`Voice updated to ${found.name}, BOSS.`);
    }
  });
}

// Update speech rate display
const speechRateInput = document.getElementById('speech-rate');
const speechRateVal = document.getElementById('speech-rate-val');
speechRateInput.addEventListener('input', (e) => {
  speechRateVal.textContent = parseFloat(e.target.value).toFixed(1) + 'x';
});

// Update speech pitch display
const speechPitchInput = document.getElementById('speech-pitch');
const speechPitchVal = document.getElementById('speech-pitch-val');
speechPitchInput.addEventListener('input', (e) => {
  speechPitchVal.textContent = parseFloat(e.target.value).toFixed(1);
});

function cleanTextForSpeech(text) {
  let cleaned = text;

  // 1. If text is a JSON object or stringified JSON (e.g. { "text": "...", "speech": "...", "command": {...} })
  if (typeof cleaned === 'object' && cleaned !== null) {
    cleaned = cleaned.speech || cleaned.text || '';
  } else if (typeof cleaned === 'string') {
    const trimmed = cleaned.trim();
    if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
      try {
        const parsed = JSON.parse(trimmed);
        if (parsed && (parsed.speech || parsed.text)) {
          cleaned = parsed.speech || parsed.text;
        }
      } catch (e) {
        // Fallback regex match for "speech": "..." or "text": "..."
        const match = cleaned.match(/"(?:speech|text)"\s*:\s*"([^"]+)"/);
        if (match && match[1]) {
          cleaned = match[1];
        }
      }
    }
  }

  // Convert name references to Jenny
  cleaned = String(cleaned || '').replace(/F\.R\.I\.D\.A\.Y\.?/gi, 'Jenny');
  cleaned = cleaned.replace(/Friday/gi, 'Jenny');
  
  // Remove markdown bold/italic asterisks & underscores
  cleaned = cleaned.replace(/\*\*|__|\*|_/g, '');
  
  // Omit markdown code blocks from speech synthesis completely to avoid spelling out code
  cleaned = cleaned.replace(/```[a-z]*\n[\s\S]*?\n```/g, ' ');
  cleaned = cleaned.replace(/`([^`]+)`/g, '$1');
  
  // Remove markdown headers, lists, and brackets
  cleaned = cleaned.replace(/#+\s+/g, '');
  cleaned = cleaned.replace(/^\s*[-*+]\s+/gm, '');
  cleaned = cleaned.replace(/^\s*\d+\.\s+/gm, '');
  cleaned = cleaned.replace(/[\{\}\[\]\<\>]/g, '');
  cleaned = cleaned.replace(/[-=]{3,}/g, '');
  cleaned = cleaned.replace(/\s+/g, ' ').trim();
  
  return cleaned;
}

async function speak(text, onComplete = null) {
  if (synth.speaking) {
    synth.cancel();
  }
  
  if (!text || text.trim() === '' || isVoiceMuted) {
    if (typeof onComplete === 'function') onComplete();
    return;
  }

  const cleanText = cleanTextForSpeech(text);
  if (!cleanText || cleanText.trim() === '') {
    if (typeof onComplete === 'function') onComplete();
    return;
  }

  const siriPreview = document.getElementById('siri-transcript-preview');
  if (siriPreview) {
    siriPreview.textContent = cleanText;
  }

  speechSessionId++;
  const currentSessionId = speechSessionId;

  // Check if ElevenLabs API key is saved in localStorage or environment
  const elevenApiKey = localStorage.getItem('elevenlabs_api_key');
  if (elevenApiKey) {
    try {
      setCoreState('speaking');
      isSpeaking = true;
      if (isListening) safeStopRecognition();

      const selectedOption = voiceSelect?.selectedOptions[0];
      const selectedElevenId = selectedOption?.getAttribute('data-elevenlabs-id') || 'OUBnvvuqEKdDWtapoJFn';

      const response = await fetch('/api/tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: cleanText,
          voiceId: selectedElevenId,
          apiKey: elevenApiKey
        })
      });

      if (response.ok && response.headers.get('content-type')?.includes('audio/mpeg')) {
        const audioBlob = await response.blob();
        const audioUrl = URL.createObjectURL(audioBlob);
        const audio = new Audio(audioUrl);

        audio.onended = () => {
          if (currentSessionId !== speechSessionId) return;
          isSpeaking = false;
          setCoreState('idle');
          if (typeof onComplete === 'function') { try { onComplete(); } catch (e) {} }
          setTimeout(() => {
            if (currentSessionId === speechSessionId && !isSpeaking && !isListening) safeStartRecognition();
          }, 400);
        };

        audio.onerror = () => {
          fallbackWebSpeech(cleanText, currentSessionId, onComplete);
        };

        await audio.play();
        return;
      }
    } catch (e) {
      console.warn("ElevenLabs TTS stream fallback:", e);
    }
  }

  fallbackWebSpeech(cleanText, currentSessionId, onComplete);
}

function fallbackWebSpeech(cleanText, currentSessionId, onComplete) {
  const utterance = new SpeechSynthesisUtterance(cleanText);
  if (selectedVoice) {
    utterance.voice = selectedVoice;
  }
  
  utterance.rate = (speechRateInput && parseFloat(speechRateInput.value)) || 1.0;
  utterance.pitch = (speechPitchInput && parseFloat(speechPitchInput.value)) || 1.0;
  
  utterance.onstart = () => {
    if (currentSessionId !== speechSessionId) return;
    isSpeaking = true;
    setCoreState('speaking');
    
    if (isListening) {
      safeStopRecognition();
    }
  };
  
  utterance.onend = () => {
    if (currentSessionId !== speechSessionId) return;
    isSpeaking = false;
    setCoreState('idle');
    
    if (typeof onComplete === 'function') {
      try { onComplete(); } catch (e) {}
    }
    
    setTimeout(() => {
      if (currentSessionId === speechSessionId && !isSpeaking && !isListening) {
        safeStartRecognition();
      }
    }, 400);
  };
  
  utterance.onerror = (event) => {
    console.error('Speech error:', event);
    if (currentSessionId !== speechSessionId) return;
    isSpeaking = false;
    setCoreState('idle');
    
    if (typeof onComplete === 'function') {
      try { onComplete(); } catch (e) {}
    }

    setTimeout(() => {
      if (currentSessionId === speechSessionId && !isSpeaking && !isListening) {
        safeStartRecognition();
      }
    }, 400);
  };
  
  synth.speak(utterance);
}

// Permanent Core Audio Visualizer (Concentric procedural waves + real-time frequency spikes)
let permanentVisualizerFrameId;

function initPermanentCoreVisualizer() {
  canvas = document.getElementById('waveform-canvas');
  if (!canvas) return;
  ctx = canvas.getContext('2d');
  const center = canvas.width / 2;
  let step = 0;

  function draw() {
    permanentVisualizerFrameId = requestAnimationFrame(draw);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    const time = step * 0.05;
    step++;
    
    if (isSpeaking) {
      // 1. SPEAKING STATE: Draw smooth yellow concentric waves
      ctx.lineWidth = 2;
      const colors = [
        'rgba(250, 204, 21, 0.55)', // yellow inner
        'rgba(250, 204, 21, 0.25)',
        'rgba(250, 204, 21, 0.12)'
      ];
      
      for (let l = 0; l < 3; l++) {
        ctx.strokeStyle = colors[l];
        ctx.beginPath();
        const baseRadius = (canvas.width * 0.32) + l * 8;
        
        for (let i = 0; i <= 360; i += 3) {
          const angle = (i * Math.PI) / 180;
          const waveFreq = 8 + l * 2;
          const waveAmp = 12 - l * 2;
          const offset = Math.sin(angle * waveFreq + time * 2) * waveAmp;
          const dist = baseRadius + offset;
          const x = center + Math.cos(angle) * dist;
          const y = center + Math.sin(angle) * dist;
          if (i === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        ctx.closePath();
        ctx.stroke();
      }
    } else {
      // 2. LISTENING OR STANDBY STATE: Draw radial frequency spikes
      let dataArray = null;
      let bufferLength = 0;
      
      if (permanentAnalyser) {
        bufferLength = permanentAnalyser.frequencyBinCount;
        dataArray = new Uint8Array(bufferLength);
        permanentAnalyser.getByteFrequencyData(dataArray);
      }
      
      const numBars = 72;
      const rads = (Math.PI * 2) / numBars;
      const baseRadius = canvas.width * 0.32;
      
      // Standby vs. Active listening styles
      const activeMode = !isPassiveWakeWordActive && isListening;
      ctx.lineWidth = activeMode ? 2.5 : 1.5;
      
      // Standby uses soft pulsing cyan/purple, Active uses bright green
      const baseColor = activeMode ? 'rgba(34, 197, 94, 0.7)' : 'rgba(6, 182, 212, 0.22)';
      const spikeColor = activeMode ? 'rgba(74, 222, 128, 0.85)' : 'rgba(168, 85, 247, 0.3)';
      
      // Draw faint HUD outer dashed target ring
      ctx.strokeStyle = activeMode ? 'rgba(34, 197, 94, 0.12)' : 'rgba(6, 182, 212, 0.07)';
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 8]);
      ctx.beginPath();
      ctx.arc(center, center, baseRadius + 22, time * 0.1, time * 0.1 + Math.PI * 2);
      ctx.stroke();
      ctx.setLineDash([]); // reset dash
      
      // Draw faint HUD crosshairs
      ctx.strokeStyle = activeMode ? 'rgba(34, 197, 94, 0.08)' : 'rgba(6, 182, 212, 0.05)';
      ctx.lineWidth = 1;
      
      // Left crosshair tick
      ctx.beginPath();
      ctx.moveTo(center - baseRadius - 15, center);
      ctx.lineTo(center - baseRadius + 5, center);
      ctx.stroke();
      
      // Right crosshair tick
      ctx.beginPath();
      ctx.moveTo(center + baseRadius - 5, center);
      ctx.lineTo(center + baseRadius + 15, center);
      ctx.stroke();
      
      // Top crosshair tick
      ctx.beginPath();
      ctx.moveTo(center, center - baseRadius - 15);
      ctx.lineTo(center, center - baseRadius + 5);
      ctx.stroke();
      
      // Bottom crosshair tick
      ctx.beginPath();
      ctx.moveTo(center, center + baseRadius - 5);
      ctx.lineTo(center, center + baseRadius + 15);
      ctx.stroke();

      for (let i = 0; i < numBars; i++) {
        const angle = i * rads + time * 0.2; // slow rotation
        let barHeight = 0;
        
        if (dataArray) {
          const dataIndex = Math.floor((i / numBars) * (bufferLength * 0.5));
          const rawVal = dataArray[dataIndex] || 0;
          const sensitivity = activeMode ? 0.32 : 0.08;
          barHeight = rawVal * sensitivity;
        }
        
        const breathingOffset = Math.sin(time * 0.5 + i * 0.1) * (activeMode ? 3 : 1.5);
        const finalBarHeight = Math.max(1, barHeight + breathingOffset + 2);
        
        const startDist = baseRadius;
        const endDist = baseRadius + finalBarHeight;
        
        const xStart = center + Math.cos(angle) * startDist;
        const yStart = center + Math.sin(angle) * startDist;
        const xEnd = center + Math.cos(angle) * endDist;
        const yEnd = center + Math.sin(angle) * endDist;
        
        ctx.strokeStyle = finalBarHeight > 6 ? spikeColor : baseColor;
        
        ctx.beginPath();
        ctx.moveTo(xStart, yStart);
        ctx.lineTo(xEnd, yEnd);
        ctx.stroke();
      }
      
      // Draw sub-rings for details
      ctx.strokeStyle = activeMode ? 'rgba(34, 197, 94, 0.15)' : 'rgba(6, 182, 212, 0.08)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(center, center, baseRadius - 8, 0, Math.PI * 2);
      ctx.stroke();
    }
  }
  
  draw();
}

// Assistant Central Core State Control
const assistantCoreContainer = document.querySelector('.assistant-core-container');
const coreStatus = document.getElementById('core-status');
const micIcon = document.getElementById('mic-icon');

function setCoreState(state) {
  assistantCoreContainer.className = 'assistant-core-container';
  assistantCoreContainer.classList.add('state-' + state);
  
  if (state === 'idle' || state === 'passive-listen') {
    coreStatus.textContent = 'JENNY READY (CLICK TO SPEAK)';
    micIcon.className = 'fa-solid fa-microphone-slash';
  } else if (state === 'listening') {
    coreStatus.textContent = 'LISTENING FOR COMMAND...';
    micIcon.className = 'fa-solid fa-microphone';
    playBeep(440, 0.1, 'sine');
  } else if (state === 'thinking') {
    coreStatus.textContent = 'THINKING...';
    micIcon.className = 'fa-solid fa-circle-notch fa-spin';
  } else if (state === 'speaking') {
    coreStatus.textContent = 'SPEAKING';
    micIcon.className = 'fa-solid fa-volume-high';
  }
}

let isRecognitionActive = false;

function safeStartRecognition() {
  if (!recognition || isSpeaking || isVoiceMuted || isRecognitionActive) return;
  try {
    isRecognitionActive = true;
    recognition.start();
  } catch (e) {
    isRecognitionActive = false;
  }
}

function safeStopRecognition() {
  if (!recognition) return;
  try {
    isRecognitionActive = false;
    recognition.stop();
  } catch (e) {}
}

// SPEECH RECOGNITION SETUP (ChatGPT voice mode dictation wrapper)
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
if (SpeechRecognition) {
  recognition = new SpeechRecognition();
  recognition.continuous = false;
  // Enable interim results for real-time dictation visual feedback
  recognition.interimResults = true;
  recognition.lang = 'en-US';
  
  recognition.onstart = () => {
    isListening = true;
    isRecognitionActive = true;
    receivedSpeechThisSession = false;
    logToMind('[Acoustic Engine] Vocal stream connection initialized.');
    
    if (isPassiveWakeWordActive) {
      setCoreState('passive-listen');
      const detBox = document.getElementById('speech-detection-text');
      if (detBox) {
        detBox.textContent = "Awaiting 'Hey Friday' wake word...";
        detBox.style.color = 'var(--text-muted)';
      }
    } else {
      setCoreState('listening');
      const detBox = document.getElementById('speech-detection-text');
      if (detBox) {
        detBox.textContent = "Listening... Speak command, BOSS.";
        detBox.style.color = 'var(--text-primary)';
      }
    }
    startMicCapture();
  };
  
  recognition.onend = () => {
    isListening = false;
    isRecognitionActive = false;
    stopMicCapture();
    
    // If active conversation timed out with silence, revert to passive wake-word mode
    if (!isPassiveWakeWordActive && !receivedSpeechThisSession && !isSpeaking) {
      logToMind('[Acoustic Engine] Silence timeout detected. Reverting to passive standby.');
      isPassiveWakeWordActive = true;
    }
    
    const detBox = document.getElementById('speech-detection-text');
    if (detBox) {
      detBox.textContent = isPassiveWakeWordActive ? "Awaiting wake word..." : "Awaiting vocal input...";
      detBox.style.color = 'var(--text-secondary)';
    }
    
    if (isPassiveWakeWordActive) {
      setCoreState('passive-listen');
    } else if (!isSpeaking) {
      setCoreState('idle');
    }
    
    // Keep background listening running
    if (!isSpeaking) {
      setTimeout(() => {
        if (!isSpeaking && !isListening && !isRecognitionActive) {
          safeStartRecognition();
        }
      }, 500);
    }
  };
  
  recognition.onresult = (event) => {
    receivedSpeechThisSession = true;
    let interimTranscript = '';
    let finalTranscript = '';
    
    for (let i = event.resultIndex; i < event.results.length; ++i) {
      if (event.results[i].isFinal) {
        finalTranscript += event.results[i][0].transcript;
      } else {
        interimTranscript += event.results[i][0].transcript;
      }
    }
    
    // Update input bar and detected speech box in real-time
    const currentDictation = finalTranscript || interimTranscript;
    if (currentDictation) {
      terminalInput.value = currentDictation;
      const detBox = document.getElementById('speech-detection-text');
      if (detBox) {
        detBox.textContent = `"${currentDictation}"`;
        detBox.style.color = '#00f3ff';
      }
      const siriPreview = document.getElementById('siri-transcript-preview');
      if (siriPreview) {
        siriPreview.textContent = `"${currentDictation}"`;
      }
      const siriPrompt = document.getElementById('siri-prompt-title');
      if (siriPrompt) {
        siriPrompt.textContent = "Listening to input...";
      }
    }
    
    // Process final transcript: Auto-submit speech input & execute command
    if (finalTranscript) {
      logToConsole(finalTranscript, 'user');
      logToMind(`[Acoustic Engine] Transcribed Final: "${finalTranscript}"`);
      const detBox = document.getElementById('speech-detection-text');
      if (detBox) {
        detBox.textContent = `"${finalTranscript}"`;
        detBox.style.color = '#00f3ff';
      }
      
      const siriPrompt = document.getElementById('siri-prompt-title');
      if (siriPrompt) {
        siriPrompt.textContent = `Command: "${finalTranscript}"`;
      }

      // Submit input and execute command
      handleCommand(finalTranscript);

      // Stop mic recognition immediately so it turns OFF after command
      safeStopRecognition();
      setCoreState('idle');
      const floatState = document.getElementById('floating-mic-state');
      const menubarState = document.getElementById('menubar-mic-status');
      const siriDot = document.getElementById('siri-status-dot');
      const siriBadge = document.getElementById('siri-badge-text');

      if (floatState) floatState.textContent = 'READY (CLICK TO SPEAK)';
      if (menubarState) menubarState.innerHTML = '<i class="fa-solid fa-microphone"></i> SPEAK TO JENNY';
      if (siriDot) siriDot.classList.remove('listening');
      if (siriBadge) siriBadge.textContent = 'SIRI / JENNY NEURAL LINK';
    }
  };
  
  recognition.onerror = (event) => {
    if (event.error === 'not-allowed') {
      logToConsole("Microphone access not allowed, BOSS. Please enable microphone permissions in your browser address bar.", "error");
      logToMind("[Acoustic Engine] Permission blocked. Disabling auto-restart thread.");
      document.getElementById('continuous-listen').checked = false;
      sfx.error();
    } else if (event.error !== 'no-speech') {
      logToConsole(`Voice error: ${event.error}`, 'error');
      logToMind(`[Acoustic Engine] Stream error: ${event.error}`);
      sfx.error();
    }
    isListening = false;
    setCoreState('idle');
    stopMicCapture();
  };
}

// Microphone Analyser (Live wave rendering + Core resizing)
async function startMicCapture() {
  try {
    if (audioCtx.state === 'suspended') {
      await audioCtx.resume();
    }
    
    micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    micSource = audioCtx.createMediaStreamSource(micStream);
    micAnalyser = audioCtx.createAnalyser();
    micAnalyser.fftSize = 128;
    micSource.connect(micAnalyser);
    
    startListeningWaveformAnimation();
  } catch (err) {
    logToMind(`[OS Audio] Microphone capture link blocked: ${err.message}`);
  }
}

function stopMicCapture() {
  cancelAnimationFrame(listeningWaveformFrameId);
  if (micStream) {
    micStream.getTracks().forEach(track => track.stop());
  }
  micStream = null;
  document.getElementById('assistant-core').style.transform = '';
  ctx.clearRect(0, 0, canvas.width, canvas.height);
}

function startListeningWaveformAnimation() {
  const bufferLength = micAnalyser.frequencyBinCount;
  const dataArray = new Uint8Array(bufferLength);
  
  function draw() {
    if (!isListening) return;
    
    listeningWaveformFrameId = requestAnimationFrame(draw);
    micAnalyser.getByteFrequencyData(dataArray);
    
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.lineWidth = 2;
    ctx.strokeStyle = 'rgba(74, 222, 128, 0.6)'; // Neon green for listening
    
    const center = canvas.width / 2;
    let total = 0;
    
    ctx.beginPath();
    for (let i = 0; i <= 360; i += 3) {
      const angle = (i * Math.PI) / 180;
      
      // Index mapping to read frequencies around circle
      const dataIndex = Math.floor((i / 360) * bufferLength);
      const val = dataArray[dataIndex] || 0;
      total += val;
      
      const radius = 100 + (val / 255) * 35;
      const x = center + Math.cos(angle) * radius;
      const y = center + Math.sin(angle) * radius;
      
      if (i === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    }
    ctx.closePath();
    ctx.stroke();
    
    // Scale central orb to user voice volume
    const average = total / (360 / 3 + 1);
    const scale = 1 + (average / 255) * 0.45;
    document.getElementById('assistant-core').style.transform = `scale(${scale})`;
  }
  
  draw();
}

// Click core to manually trigger listening or speak start
const coreTrigger = document.getElementById('assistant-core-trigger');
coreTrigger.addEventListener('click', () => {
  sfx.click();
  if (audioCtx.state === 'suspended') {
    audioCtx.resume();
  }
  
  if (isSpeaking) {
    synth.cancel();
    isSpeaking = false;
    setCoreState('idle');
    return;
  }
  
  if (isListening) {
    document.getElementById('continuous-listen').checked = false;
    isPassiveWakeWordActive = true; // revert to standby
    safeStopRecognition();
  } else if (recognition) {
    isPassiveWakeWordActive = false; // force active listening mode on manual click!
    safeStartRecognition();
  } else {
    speak("Voice command recognition is not supported in this browser, BOSS. Please use the text terminal.");
  }
});

// TERMINAL / CONSOLE LOGGING
const consoleLogs = document.getElementById('console-logs');
const terminalInput = document.getElementById('terminal-input');
const terminalSendBtn = document.getElementById('terminal-send-btn');

function logToConsole(text, type = 'system') {
  const timestamp = new Date().toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
  const entry = document.createElement('div');
  entry.className = `log-entry ${type}`;
  
  if (type === 'assistant') {
    // ChatGPT visual text typewriter streaming
    entry.innerHTML = `<span class="timestamp">[${timestamp}]</span> <span class="assistant-content"></span>`;
    consoleLogs.appendChild(entry);
    typewriterPrint(text, entry.querySelector('.assistant-content'));
  } else {
    entry.innerHTML = `<span class="timestamp">[${timestamp}]</span> ${text}`;
    consoleLogs.appendChild(entry);
    consoleLogs.scrollTop = consoleLogs.scrollHeight;
  }
}

function typewriterPrint(text, container) {
  let idx = 0;
  const speed = 10; // 10ms typing speed
  
  function type() {
    if (idx < text.length) {
      // Handle raw character insertion (including spaces)
      container.textContent += text.charAt(idx);
      idx++;
      consoleLogs.scrollTop = consoleLogs.scrollHeight;
      setTimeout(type, speed);
    }
  }
  type();
}

// AGENT MIND THOUGHT CONSOLE
const mindLogs = document.getElementById('mind-logs');
function logToMind(text) {
  const timestamp = new Date().toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
  const entry = document.createElement('div');
  entry.className = `log-entry mind`;
  entry.innerHTML = `<span class="timestamp">[${timestamp}]</span> ${text}`;
  
  mindLogs.appendChild(entry);
  mindLogs.scrollTop = mindLogs.scrollHeight;
}

function submitTerminalCommand() {
  const cmd = terminalInput.value.trim();
  if (cmd === '') return;
  
  sfx.click();
  logToConsole(cmd, 'user');
  logToMind(`[Console Input] Registered: "${cmd}"`);
  terminalInput.value = '';
  handleCommand(cmd);
}

terminalSendBtn.addEventListener('click', submitTerminalCommand);
terminalInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    submitTerminalCommand();
  }
});

// COMMAND PROCESSOR
async function handleCommand(commandString) {
  setCoreState('thinking');
  const cmdClean = commandString.trim();
  const cmdLower = cmdClean.toLowerCase();
  
  // GREETINGS
  if (cmdLower.includes('hello friday') || cmdLower.includes('wake up friday') || cmdLower.includes('wake up jarvis')) {
    logToMind('[Cognitive Mind] Trigger matched: Greeting sequence.');
    sfx.confirm();
    speak("Fully functional and at your service, BOSS. Systems are optimal.");
    return;
  }

  // GOOGLE SEARCH DIRECTIVE
  if (cmdLower.startsWith('google ') || cmdLower.startsWith('search google for ') || cmdLower.startsWith('search ')) {
    logToMind('[Cognitive Mind] Directive parsed: Web Search.');
    let query = '';
    if (cmdLower.startsWith('search google for ')) query = cmdClean.substring(18);
    else if (cmdLower.startsWith('google ')) query = cmdClean.substring(7);
    else query = cmdClean.substring(7);
    
    query = query.trim();
    if (query) {
      sfx.confirm();
      const searchUrl = `https://www.google.com/search?q=${encodeURIComponent(query)}`;
      logToMind(`[System Action] Opening Google search window: "${query}"`);
      window.open(searchUrl, '_blank');
      speak(`Searching Google for ${query}, BOSS.`);
      setCoreState('idle');
      return;
    }
  }

  // SYSTEM CONTROL: VOLUME
  if (cmdLower.includes('volume ') || cmdLower === 'mute' || cmdLower === 'unmute') {
    logToMind('[Cognitive Mind] Directive parsed: PC Volume Adjustments.');
    let value = '';
    
    if (cmdLower.includes('mute')) value = 'mute';
    else if (cmdLower.includes('unmute')) value = 'unmute';
    else {
      const match = cmdLower.match(/(\d+)/);
      if (match) value = match[1];
    }
    
    if (value) {
      logToMind(`[System Action] Dispatching volume control action: "${value}"`);
      try {
        const response = await fetch('/api/control', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action: 'volume', value })
        });
        const data = await response.json();
        if (data.success) {
          sfx.confirm();
          logToMind(`[System Action] Volume action executed successfully.`);
          speak(value === 'mute' ? "Muted system, BOSS." : value === 'unmute' ? "System unmuted, BOSS." : `Volume set to ${value} percent, BOSS.`);
        } else {
          sfx.error();
          speak("System volume adjustment blocked by platform OS, BOSS.");
        }
      } catch (err) {
        sfx.error();
        logToMind(`[System Action] Volume control link error: ${err.message}`);
        speak("Unable to reach system control bridge.");
      }
      return;
    }
  }

  // SYSTEM CONTROL: BRIGHTNESS
  if (cmdLower.includes('brightness ')) {
    logToMind('[Cognitive Mind] Directive parsed: PC Brightness Adjustments.');
    let value = '';
    const match = cmdLower.match(/(\d+)/);
    if (match) value = match[1];
    
    if (value) {
      logToMind(`[System Action] Dispatching brightness control action: "${value}"`);
      try {
        const response = await fetch('/api/control', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action: 'brightness', value })
        });
        const data = await response.json();
        if (data.success) {
          sfx.confirm();
          logToMind(`[System Action] Brightness action executed successfully.`);
          speak(`Brightness set to ${value} percent, BOSS.`);
        } else {
          sfx.error();
          speak("System brightness adjustment failed, BOSS.");
        }
      } catch (err) {
        sfx.error();
        logToMind(`[System Action] Brightness control link error: ${err.message}`);
        speak("Unable to reach system control bridge.");
      }
      return;
    }
  }

  // SYSTEM CONTROL: RESTART / SHUTDOWN
  if (cmdLower.includes('restart my pc') || cmdLower.includes('restart computer') || cmdLower.includes('reboot computer') || cmdLower.includes('reboot pc')) {
    logToMind('[Cognitive Mind] Directive parsed: PC Restart sequence.');
    try {
      speak("Restarting workstation. Standby, BOSS.");
      setTimeout(async () => {
        await fetch('/api/control', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action: 'restart' })
        });
      }, 1500);
    } catch (e) {
      sfx.error();
    }
    return;
  }

  if (cmdLower.includes('shutdown my pc') || cmdLower.includes('shutdown computer') || cmdLower.includes('shut down computer') || cmdLower.includes('power off pc') || cmdLower.includes('power off computer')) {
    logToMind('[Cognitive Mind] Directive parsed: PC Shutdown sequence.');
    try {
      speak("Powering down all systems. Until next time, BOSS.");
      setTimeout(async () => {
        await fetch('/api/control', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action: 'shutdown' })
        });
      }, 1500);
    } catch (e) {
      sfx.error();
    }
    return;
  }

  // SYSTEM DIAGNOSTICS / STATUS
  if (cmdLower.includes('system status') || cmdLower.includes('diagnostics') || cmdLower.includes('battery status') || cmdLower.includes('cpu usage') || cmdLower.includes('memory usage') || cmdLower.includes('battery level')) {
    logToMind('[Cognitive Mind] Directive parsed: Get System Diagnostics.');
    try {
      const response = await fetch('/api/system');
      const data = await response.json();
      if (data.success) {
        sfx.confirm();
        let batteryText = data.data.battery !== 'Unknown' ? `Battery is at ${data.data.battery.percent} percent and is ${data.data.battery.state}.` : '';
        let brightnessText = data.data.brightness !== 'Unknown' ? `Brightness is at ${Math.round(data.data.brightness * 100)} percent.` : '';
        let sysText = `System load is normal, BOSS. CPU is at ${data.data.cpu} percent, RAM usage is ${data.data.ram} percent. ${brightnessText} ${batteryText}`;
        speak(sysText);
        logToConsole(sysText, 'assistant');
      } else {
        sfx.error();
        speak("I was unable to retrieve system diagnostics, BOSS.");
      }
    } catch (e) {
      sfx.error();
      speak("System bridge is unresponsive.");
    }
    return;
  }

  // SYSTEM CONTROL: SCREENSHOT
  if (cmdLower === 'screenshot' || cmdLower === 'take screenshot') {
    logToMind('[Cognitive Mind] Directive parsed: Take macOS Screenshot.');
    try {
      logToConsole("Requesting backend to capture screen...", 'system');
      const response = await fetch('/api/control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'screenshot' })
      });
      const data = await response.json();
      if (data.success) {
        sfx.confirm();
        speak("Screenshot captured and saved to Desktop, BOSS.");
        logToConsole(data.message, 'success');
      } else {
        sfx.error();
        speak("Failed to capture screenshot, BOSS.");
      }
    } catch (e) {
      sfx.error();
      speak("Screenshot bridge communication error.");
    }
    return;
  }

  // SYSTEM CONTROL: EMPTY TRASH
  if (cmdLower === 'empty trash' || cmdLower === 'clear trash') {
    logToMind('[Cognitive Mind] Directive parsed: Empty Finder trash.');
    try {
      logToConsole("Requesting backend to empty system trash...", 'system');
      const response = await fetch('/api/control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'empty-trash' })
      });
      const data = await response.json();
      if (data.success) {
        sfx.confirm();
        speak("Finder trash emptied successfully, BOSS.");
        logToConsole("System trash cleared.", 'success');
      } else {
        sfx.error();
        speak("Failed to empty system trash, BOSS.");
      }
    } catch (e) {
      sfx.error();
      speak("Trash bridge communication error.");
    }
    return;
  }

  // LOCAL INTERACTIVE: JOKE
  if (cmdLower === 'tell me a joke' || cmdLower === 'tell a joke') {
    logToMind('[Cognitive Mind] Directive matched: Local Humor Subsystem.');
    const jokes = [
      "Why did the database administrator leave the restaurant? Because there were too many tables.",
      "How many programmers does it take to change a light bulb? None, that's a hardware problem.",
      "There are 10 types of people in this world: those who understand binary, and those who don't.",
      "Why do programmers wear glasses? Because they cannot C#.",
      "What is an optimist's favorite computer part? The space bar."
    ];
    const randomJoke = jokes[Math.floor(Math.random() * jokes.length)];
    sfx.confirm();
    speak(randomJoke);
    logToConsole(`[Friday Humor] ${randomJoke}`, 'assistant');
    return;
  }

  // LOCAL INTERACTIVE: COIN FLIP
  if (cmdLower === 'flip a coin' || cmdLower === 'flip coin') {
    logToMind('[Cognitive Mind] Directive matched: Coin Flip Simulator.');
    const result = Math.random() < 0.5 ? "HEADS" : "TAILS";
    sfx.confirm();
    speak(`The coin landed on ${result}, BOSS.`);
    logToConsole(`[System Result] Coin Flip: ${result}`, 'success');
    return;
  }

  // LOCAL INTERACTIVE: ROLL DIE
  if (cmdLower === 'roll a die' || cmdLower === 'roll die' || cmdLower === 'roll dice') {
    logToMind('[Cognitive Mind] Directive matched: Dice Roll Simulator.');
    const roll = Math.floor(Math.random() * 6) + 1;
    sfx.confirm();
    speak(`You rolled a ${roll}, BOSS.`);
    logToConsole(`[System Result] Dice Roll: ${roll}`, 'success');
    return;
  }

  // SYSTEM CONTROL: MEDIA (Music Playback)
  if (cmdLower.includes('music') || cmdLower.includes('song') || cmdLower.includes('track') || cmdLower === 'play' || cmdLower === 'pause' || cmdLower === 'next' || cmdLower === 'previous') {
    logToMind('[Cognitive Mind] Directive parsed: Media Playback controls.');
    let value = '';
    if (cmdLower.includes('play') || cmdLower.includes('resume')) value = 'play';
    else if (cmdLower.includes('pause') || cmdLower.includes('stop music')) value = 'play'; 
    else if (cmdLower.includes('next') || cmdLower.includes('skip')) value = 'next';
    else if (cmdLower.includes('prev')) value = 'previous';
    
    if (value) {
      logToMind(`[System Action] Dispatching music command: "${value}"`);
      try {
        const response = await fetch('/api/control', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action: 'media', value })
        });
        const data = await response.json();
        if (data.success) {
          sfx.confirm();
          speak("Media directive executed, BOSS.");
        } else {
          sfx.error();
          speak("No active media engine detected, BOSS.");
        }
      } catch (err) {
        sfx.error();
        speak("Media bridge communication failure.");
      }
      return;
    }
  }

  // SYSTEM CONTROL: LOCK SCREEN & SLEEP
  if (cmdLower.includes('lock my pc') || cmdLower.includes('lock screen') || cmdLower.includes('lock computer')) {
    logToMind('[Cognitive Mind] Directive parsed: Security locking sequence.');
    try {
      const response = await fetch('/api/control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'lock' })
      });
      const data = await response.json();
      if (data.success) {
        sfx.confirm();
        speak("Securing workstation. Good luck, BOSS.");
      }
    } catch (e) {
      sfx.error();
    }
    return;
  }

  if (cmdLower.includes('sleep pc') || cmdLower.includes('put screen to sleep')) {
    logToMind('[Cognitive Mind] Directive parsed: Power saving sequence.');
    try {
      speak("System display powering down, BOSS.");
      setTimeout(async () => {
        await fetch('/api/control', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action: 'sleep' })
        });
      }, 1000);
    } catch (e) {}
    return;
  }

  // SYSTEM CONTROL: SPOTIFY PLAYBACK
  if (cmdLower.includes('spotify') && (cmdLower.includes('play') || cmdLower.includes('playlist') || cmdLower.includes('song') || cmdLower.includes('music'))) {
    logToMind('[Cognitive Mind] Directive parsed: Spotify music search & playback.');
    let query = '';
    if (cmdLower.startsWith('spotify play ')) {
      query = cmdClean.substring(13).trim();
    } else if (cmdLower.includes(' on spotify')) {
      const playIdx = cmdLower.indexOf('play ');
      const onIdx = cmdLower.indexOf(' on spotify');
      if (playIdx !== -1 && onIdx !== -1 && playIdx < onIdx) {
        query = cmdClean.substring(playIdx + 5, onIdx).trim();
      } else {
        query = cmdClean.replace(/spotify/gi, '').replace(/play/gi, '').trim();
      }
    } else {
      query = cmdClean.replace(/spotify/gi, '').replace(/play/gi, '').trim();
    }
    
    if (query) {
      logToMind(`[System Action] Dispatching Spotify request: "${query}"`);
      try {
        const response = await fetch('/api/control', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action: 'spotify', value: query })
        });
        const data = await response.json();
        if (data.success) {
          sfx.confirm();
          speak(`Launching Spotify and playing ${query}, BOSS.`);
        } else {
          sfx.error();
          speak("Spotify command could not be executed, BOSS.");
        }
      } catch (err) {
        sfx.error();
        speak("Spotify bridge connection failed.");
      }
      return;
    }
  }

  // WIDGET DYNAMICS: SECURE MEMORY VAULT COMMANDS
  if (cmdLower.startsWith('remember ') || cmdLower.startsWith('save ') || cmdLower.startsWith('write down ')) {
    logToMind('[Cognitive Mind] Directive matched: Save item to memory vault.');
    let fact = '';
    if (cmdLower.startsWith('remember ')) fact = cmdClean.substring(9);
    else if (cmdLower.startsWith('save ')) fact = cmdClean.substring(5);
    else fact = cmdClean.substring(11);
    
    if (fact.trim()) {
      sfx.confirm();
      addVaultItem(fact.trim());
    } else {
      sfx.error();
      speak("Vault payload is empty, BOSS.");
    }
    return;
  }

  if (cmdLower.includes('what did i tell you to') || cmdLower.includes('list vault') || cmdLower.includes('show vault') || cmdLower.includes('what is in my vault')) {
    logToMind('[Cognitive Mind] Directive matched: Load and speak memory vault.');
    readVaultAloud();
    return;
  }

  if (cmdLower.includes('clear vault') || cmdLower.includes('delete vault')) {
    logToMind('[Cognitive Mind] Directive matched: Clear vault database.');
    sfx.confirm();
    clearVault();
    return;
  }

  // WIDGET DYNAMICS: TO-DO LIST COMMANDS
  if (cmdLower.startsWith('add todo ') || cmdLower.startsWith('add task ') || cmdLower.includes('add to do ')) {
    logToMind('[Cognitive Mind] Task Matrix: Add checklist item.');
    let task = '';
    if (cmdLower.startsWith('add todo ')) task = cmdClean.substring(9);
    else if (cmdLower.startsWith('add task ')) task = cmdClean.substring(9);
    else {
      const idx = cmdLower.indexOf('add to do ');
      task = cmdClean.substring(idx + 10);
    }
    
    if (task.trim()) {
      sfx.confirm();
      addTodoItem(task.trim());
      speak(`Task added: ${task.trim()}, BOSS.`);
    } else {
      sfx.error();
      speak("Task content seems empty, BOSS.");
    }
    return;
  }

  if (cmdLower.includes('clear all tasks') || cmdLower.includes('clear to do') || cmdLower.includes('clear todo')) {
    logToMind('[Cognitive Mind] Task Matrix: Clear checklist.');
    sfx.confirm();
    clearAllTodos();
    speak("Todo matrix cleared, BOSS.");
    return;
  }

  // WIDGET DYNAMICS: COUNTDOWN COMMANDS
  if (cmdLower.includes('set countdown') || cmdLower.includes('countdown target')) {
    logToMind('[Cognitive Mind] Clock: Set Countdown Target.');
    let dateStr = '';
    let label = 'NEXT OPERATION';
    
    const nameMatch = cmdClean.match(/named\s+(.+)$/i) || cmdClean.match(/labeled\s+(.+)$/i);
    if (nameMatch) {
      label = nameMatch[1];
    }
    
    const datePartMatch = cmdClean.match(/countdown\s+(?:to|for)\s+(.+?)(?:\s+named|\s+labeled|$)/i);
    if (datePartMatch) {
      dateStr = datePartMatch[1];
    }

    if (dateStr) {
      const parsedDate = Date.parse(dateStr);
      if (!isNaN(parsedDate)) {
        sfx.confirm();
        setCountdownTarget(parsedDate, label);
        speak(`Countdown target established for ${label}, BOSS.`);
        return;
      }
    }
    
    sfx.click();
    document.getElementById('countdown-settings-panel').classList.remove('hidden');
    speak("Please insert the countdown parameters in the visual interface, BOSS.");
    setCoreState('idle');
    return;
  }

  // WIDGET DYNAMICS: TIMER COMMANDS
  if (cmdLower.includes('timer for ') || cmdLower.includes('set timer ') || cmdLower.includes('start timer ')) {
    logToMind('[Cognitive Mind] Clock: Set Timer.');
    const numMatch = cmdLower.match(/(\d+)\s*(minute|second|min|sec|hour|hr)/);
    if (numMatch) {
      const value = parseInt(numMatch[1], 10);
      const unit = numMatch[2];
      let totalSeconds = 0;
      
      if (unit.startsWith('min') || unit.startsWith('minute')) {
        totalSeconds = value * 60;
      } else if (unit.startsWith('sec') || unit.startsWith('second')) {
        totalSeconds = value;
      } else if (unit.startsWith('hour') || unit.startsWith('hr')) {
        totalSeconds = value * 3600;
      }
      
      if (totalSeconds > 0) {
        sfx.confirm();
        startTimer(totalSeconds);
        speak(`Timer activated for ${value} ${unit}s, BOSS.`);
        return;
      }
    }
    
    if (cmdLower.includes('stop timer') || cmdLower.includes('pause timer')) {
      sfx.confirm();
      pauseTimer();
      speak("Timer paused, BOSS.");
      return;
    }
    if (cmdLower.includes('reset timer')) {
      sfx.confirm();
      resetTimer();
      speak("Timer reset, BOSS.");
      return;
    }
  }

  // WIDGET DYNAMICS: STOPWATCH COMMANDS
  if (cmdLower.includes('stopwatch') || cmdLower.includes('chronometer')) {
    logToMind('[Cognitive Mind] Clock: Chronometer operations.');
    if (cmdLower.includes('start') || cmdLower.includes('resume')) {
      sfx.confirm();
      startStopwatch();
      speak("Chronometer active, BOSS.");
      return;
    }
    if (cmdLower.includes('stop') || cmdLower.includes('pause')) {
      sfx.confirm();
      stopStopwatch();
      speak("Chronometer stopped, BOSS.");
      return;
    }
    if (cmdLower.includes('lap')) {
      sfx.confirm();
      lapStopwatch();
      return;
    }
    if (cmdLower.includes('reset')) {
      sfx.confirm();
      resetStopwatch();
      speak("Chronometer reset, BOSS.");
      return;
    }
  }

  // SPATIAL HUD WINDOW CONTROLS
  if (cmdLower.includes('close window') || cmdLower.includes('close all windows') || cmdLower.includes('hide window')) {
    closeSpatialWindow();
    speak("Closing spatial window overlay, BOSS.");
    return;
  }

  if (cmdLower.startsWith('open ') || cmdLower.startsWith('show ')) {
    if (cmdLower.includes('todo') || cmdLower.includes('task')) {
      openWidgetWindow('widget-todo');
      speak("Opening To-Do list spatial window, BOSS.");
      return;
    }
    if (cmdLower.includes('project') || cmdLower.includes('milestone') || cmdLower.includes('progression')) {
      openWidgetWindow('widget-project-progress');
      speak("Opening Project Progression Matrix spatial window, BOSS.");
      return;
    }
    if (cmdLower.includes('timer')) {
      openWidgetWindow('widget-timer');
      speak("Opening Countdown Timer spatial window, BOSS.");
      return;
    }
    if (cmdLower.includes('stopwatch') || cmdLower.includes('chronometer')) {
      openWidgetWindow('widget-stopwatch');
      speak("Opening Chronometer spatial window, BOSS.");
      return;
    }
    if (cmdLower.includes('vault') || cmdLower.includes('memory')) {
      openWidgetWindow('widget-vault');
      speak("Opening Secure Memory Vault spatial window, BOSS.");
      return;
    }
    if (cmdLower.includes('countdown') || cmdLower.includes('event')) {
      openWidgetWindow('widget-countdown');
      speak("Opening Event Countdown spatial window, BOSS.");
      return;
    }
    if (cmdLower.includes('protocol')) {
      openWidgetWindow('widget-protocols');
      speak("Opening System Protocols spatial window, BOSS.");
      return;
    }
  }

  // SYSTEM: OPEN WEBSITE / APP PROTOCOL
  if (cmdLower.startsWith('open ') || cmdLower.startsWith('go to ')) {
    logToMind('[Cognitive Mind] Routing query to open app/website bridge.');
    let target = '';
    if (cmdLower.startsWith('open ')) target = cmdClean.substring(5).trim();
    else if (cmdLower.startsWith('go to ')) target = cmdClean.substring(6).trim();
    
    if (target) {
      const webMappings = {
        'amazon': 'amazon.com',
        'flipkart': 'flipkart.com',
        'google': 'google.com',
        'youtube': 'youtube.com',
        'gmail': 'mail.google.com',
        'email': 'mail.google.com',
        'facebook': 'facebook.com',
        'twitter': 'twitter.com',
        'github': 'github.com',
        'reddit': 'reddit.com',
        'netflix': 'netflix.com',
        'wikipedia': 'wikipedia.org',
        'chatgpt': 'chatgpt.com',
        'discord': 'discord.com',
        'spotify': 'open.spotify.com'
      };
      
      const targetLower = target.toLowerCase();
      
      if (webMappings[targetLower] || targetLower.includes('.') || targetLower.includes('http')) {
        let url = webMappings[targetLower] || target;
        logToMind(`[System Action] Resolving website: "${url}"`);
        try {
          logToConsole(`Requesting website URL: "${url}"`, 'system');
          const response = await fetch(`/api/open-url?url=${encodeURIComponent(url)}`);
          const data = await response.json();
          if (data.success) {
            sfx.confirm();
            speak(`Launching website ${target}, BOSS.`);
          } else {
            sfx.error();
            speak(`Unable to open website: ${targetLower}`);
          }
        } catch (e) {
          sfx.error();
          speak("Website dispatcher error, BOSS.");
        }
        return;
      }
      
      logToMind(`[System Action] Resolving local application: "${target}"`);
      try {
        logToConsole(`Requesting backend to launch app: "${target}"`, 'system');
        const response = await fetch(`/api/open-app?name=${encodeURIComponent(target)}`);
        const data = await response.json();
        if (data.success) {
          sfx.confirm();
          speak(`Opening application ${target}, BOSS.`);
        } else {
          logToMind(`[System Action] App launch failed, falling back to website search: "${targetLower}.com"`);
          logToConsole(`Application not found. Attempting to launch website "${targetLower}.com"`, 'system');
          
          const fallbackUrl = `${targetLower}.com`;
          const responseWeb = await fetch(`/api/open-url?url=${encodeURIComponent(fallbackUrl)}`);
          const dataWeb = await responseWeb.json();
          if (dataWeb.success) {
            sfx.confirm();
            speak(`Opening website ${targetLower}.com, BOSS.`);
          } else {
            sfx.error();
            speak(`I could not find application or website matching ${target}, BOSS.`);
          }
        }
      } catch (err) {
        sfx.error();
        speak("Application bridge connection error.");
      }
      return;
    }
  }

  // SYSTEM: CLOSE APP
  if (cmdLower.startsWith('close ') || cmdLower.startsWith('quit ')) {
    const appName = cmdClean.substring(6).trim();
    logToMind(`[Cognitive Mind] Shell Close: App "${appName}"`);
    try {
      logToConsole(`Requesting backend to quit app: "${appName}"`, 'system');
      const response = await fetch(`/api/close-app?name=${encodeURIComponent(appName)}`);
      const data = await response.json();
      
      if (data.success) {
        sfx.confirm();
        speak(`Closing ${appName}, BOSS.`);
      } else {
        sfx.error();
        speak(`Failed to close ${appName}, BOSS.`);
        logToConsole(data.message, 'error');
      }
    } catch (err) {
      sfx.error();
      speak("Communication link error.");
    }
    return;
  }

  // GENERAL CHAT / FALLBACK TO GEMINI (RICH TEXT CONTEXT + SNAPPY CONVERSATIONAL VOICE SUMMARY)
  try {
    logToMind('[Cognitive Mind] Routing query to Gemini neural memory server...');
    logToConsole("Processing core query...", 'system');
    
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ message: cmdClean })
    });
    const data = await response.json();
    
    if (data.success) {
      logToMind('[Cognitive Mind] Response received. Printing text streaming payload.');
      
      // Print the full rich text to screen with typewriter animation
      logToConsole(data.reply.text, 'assistant');
      
      // Speak the FULL output response text and execute agentic commands ONLY AFTER speech finishes
      if (data.reply.command) {
        speak(data.reply.text, () => {
          handleAgentCommand(data.reply.command);
        });
      } else {
        speak(data.reply.text);
      }
    } else {
      sfx.error();
      speak("My cognitive buffer encountered an error, BOSS.");
    }
  } catch (err) {
    console.error('Chat error:', err);
    sfx.error();
    speak("Core communication matrix offline. Running local query subroutines.");
    speak("I am currently disconnected from primary online networks, BOSS. App controls are still fully functional.");
  }
}

async function handleAgentCommand(commandObj) {
  const { action, value } = commandObj;
  logToMind(`[Agent Action] Dispatching autonomous command: action="${action}"`);
  
  if (action === 'vault-save') {
    const text = value && value.text;
    if (!text) return;
    
    logToConsole(`[Agent Command] Saving to memory vault: "${text}"`, 'system');
    try {
      const response = await fetch('/api/vault', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text })
      });
      const data = await response.json();
      if (data.success) {
        sfx.confirm();
        logToConsole(`[Agent Output] Memory updated: "${text}"`, 'success');
        speak("I have noted that in my memory vault, BOSS.");
        if (typeof loadVaultItems === 'function') {
          loadVaultItems();
        }
      }
    } catch (err) {
      sfx.error();
      logToConsole(`[Agent Error] Failed to update memory: ${err.message}`, 'error');
    }
    return;
  }
  
  logToConsole(`[Agent Command] Executing system protocol: ${action}...`, 'system');
  
  try {
    const response = await fetch('/api/control', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action, value })
    });
    const data = await response.json();
    if (data.success) {
      sfx.confirm();
      logToConsole(`[Agent Output] ${data.message}`, 'success');
      logToMind(`[Agent System] Command execution succeeded.`);
      speak(data.message.substring(0, 100)); // Greet confirmation
    } else {
      sfx.error();
      logToConsole(`[Agent Error] ${data.message || 'Execution blocked by platform OS'}`, 'error');
    }
  } catch (err) {
    sfx.error();
    logToConsole(`[Agent Connection Error] ${err.message}`, 'error');
  }
}


// WIDGET LOGIC: MEMORY VAULT STORAGE
const vaultList = document.getElementById('vault-list');
const vaultInput = document.getElementById('vault-input');
const vaultAddBtn = document.getElementById('vault-add-btn');
const vaultCount = document.getElementById('vault-count');

async function renderVault() {
  try {
    const response = await fetch('/api/vault');
    const data = await response.json();
    if (data.success) {
      vaultList.innerHTML = '';
      const items = data.data;
      
      if (items.length === 0) {
        vaultList.innerHTML = '<div class="empty-state">Vault database empty, BOSS.</div>';
        vaultCount.textContent = '0 DATA';
        return;
      }
      
      vaultCount.textContent = `${items.length} RECORD${items.length > 1 ? 'S' : ''}`;
      
      items.forEach((item) => {
        const div = document.createElement('div');
        div.className = 'vault-item';
        div.innerHTML = `
          <div class="vault-content">
            <i class="fa-solid fa-lock vault-icon"></i>
            <span>${item.text}</span>
          </div>
          <div style="display: flex; align-items: center; gap: 8px;">
            <span class="vault-date">${item.date}</span>
            <button class="vault-delete-btn" onclick="deleteVaultItem('${item.id}')" title="Delete"><i class="fa-solid fa-trash-can"></i></button>
          </div>
        `;
        vaultList.appendChild(div);
      });
    }
  } catch (err) {
    console.error('Vault render error:', err);
  }
}

async function addVaultItem(text) {
  logToMind(`[System Action] Saving statement to local JSON database...`);
  try {
    const response = await fetch('/api/vault', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text })
    });
    const data = await response.json();
    if (data.success) {
      renderVault();
      speak("Saved to secure vault, BOSS.");
      logToMind(`[System Action] Saved successfully: "${text}"`);
    }
  } catch (e) {
    sfx.error();
  }
}

window.deleteVaultItem = async function(id) {
  sfx.click();
  logToMind(`[System Action] Deleting record: ${id}`);
  try {
    const response = await fetch(`/api/vault?id=${id}`, { method: 'DELETE' });
    const data = await response.json();
    if (data.success) {
      renderVault();
      speak("Vault item deleted, BOSS.");
    }
  } catch (e) {}
};

async function clearVault() {
  try {
    await fetch('/api/vault', { method: 'DELETE' });
    renderVault();
    speak("Memory vault fully wiped, BOSS.");
  } catch (e) {}
}

async function readVaultAloud() {
  try {
    const response = await fetch('/api/vault');
    const data = await response.json();
    if (data.success && data.data.length > 0) {
      const textToSpeak = "You've instructed me to remember the following, BOSS: " + data.data.map(item => item.text).join(". Also, ");
      speak(textToSpeak);
    } else {
      speak("Your secure memory vault is currently empty, BOSS.");
    }
  } catch (e) {
    speak("Vault database is currently unreachable, BOSS.");
  }
}

vaultAddBtn.addEventListener('click', () => {
  const txt = vaultInput.value.trim();
  if (txt) {
    sfx.click();
    addVaultItem(txt);
    vaultInput.value = '';
  }
});
vaultInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    const txt = vaultInput.value.trim();
    if (txt) {
      sfx.click();
      addVaultItem(txt);
      vaultInput.value = '';
    }
  }
});

renderVault();


// WIDGET LOGIC: TO-DO LIST
let todoItems = JSON.parse(localStorage.getItem('friday_todos')) || [];

const todoInput = document.getElementById('todo-input');
const todoAddBtn = document.getElementById('todo-add-btn');
const todoList = document.getElementById('todo-list');
const todoCount = document.getElementById('todo-count');

function renderTodos() {
  todoList.innerHTML = '';
  
  if (todoItems.length === 0) {
    todoList.innerHTML = '<div class="empty-state">No pending operations, BOSS.</div>';
    todoCount.textContent = '0 TASKS';
    return;
  }
  
  todoCount.textContent = `${todoItems.length} TASK${todoItems.length > 1 ? 'S' : ''}`;
  
  todoItems.forEach((item, index) => {
    const div = document.createElement('div');
    div.className = `todo-item ${item.completed ? 'completed' : ''}`;
    
    div.innerHTML = `
      <div class="todo-content">
        <div class="todo-checkbox" onclick="toggleTodo(${index})">
          <i class="fa-solid fa-check"></i>
        </div>
        <span class="todo-text">${item.text}</span>
      </div>
      <button class="todo-delete-btn" onclick="deleteTodo(${index})" title="Delete"><i class="fa-solid fa-trash-can"></i></button>
    `;
    
    todoList.appendChild(div);
  });
}

function addTodoItem(text) {
  todoItems.push({ text, completed: false });
  localStorage.setItem('friday_todos', JSON.stringify(todoItems));
  renderTodos();
}

window.toggleTodo = function(index) {
  sfx.click();
  todoItems[index].completed = !todoItems[index].completed;
  localStorage.setItem('friday_todos', JSON.stringify(todoItems));
  renderTodos();
};

window.deleteTodo = function(index) {
  sfx.click();
  todoItems.splice(index, 1);
  localStorage.setItem('friday_todos', JSON.stringify(todoItems));
  renderTodos();
};

function clearAllTodos() {
  todoItems = [];
  localStorage.removeItem('friday_todos');
  renderTodos();
}

todoAddBtn.addEventListener('click', () => {
  const txt = todoInput.value.trim();
  if (txt) {
    sfx.click();
    addTodoItem(txt);
    todoInput.value = '';
  }
});
todoInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    const txt = todoInput.value.trim();
    if (txt) {
      sfx.click();
      addTodoItem(txt);
      todoInput.value = '';
    }
  }
});

renderTodos();


// WIDGET LOGIC: DATE COUNTDOWN
let countdownTarget = localStorage.getItem('friday_countdown_target') || (Date.now() + 30 * 24 * 60 * 60 * 1000); 
let countdownLabel = localStorage.getItem('friday_countdown_label') || 'NEXT MAJOR MILESTONE';

const cdLabelEl = document.getElementById('countdown-label');
const editCountdownBtn = document.getElementById('edit-countdown-btn');
const settingsPanel = document.getElementById('countdown-settings-panel');
const labelInput = document.getElementById('countdown-label-input');
const dateInput = document.getElementById('countdown-date-input');
const saveBtn = document.getElementById('save-countdown-btn');
const cancelBtn = document.getElementById('cancel-countdown-btn');

function updateCountdown() {
  const now = Date.now();
  const diff = countdownTarget - now;
  
  cdLabelEl.textContent = countdownLabel;
  
  if (diff <= 0) {
    document.getElementById('cd-days').textContent = '00';
    document.getElementById('cd-hours').textContent = '00';
    document.getElementById('cd-mins').textContent = '00';
    document.getElementById('cd-secs').textContent = '00';
    return;
  }
  
  const days = Math.floor(diff / (1000 * 60 * 60 * 24));
  const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
  const mins = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
  const secs = Math.floor((diff % (1000 * 60)) / 1000);
  
  document.getElementById('cd-days').textContent = String(days).padStart(2, '0');
  document.getElementById('cd-hours').textContent = String(hours).padStart(2, '0');
  document.getElementById('cd-mins').textContent = String(mins).padStart(2, '0');
  document.getElementById('cd-secs').textContent = String(secs).padStart(2, '0');
}

function setCountdownTarget(timestamp, label) {
  countdownTarget = timestamp;
  countdownLabel = label;
  localStorage.setItem('friday_countdown_target', timestamp);
  localStorage.setItem('friday_countdown_label', label);
  updateCountdown();
}

editCountdownBtn.addEventListener('click', () => {
  sfx.click();
  settingsPanel.classList.toggle('hidden');
  labelInput.value = countdownLabel;
  
  const dateObj = new Date(Number(countdownTarget));
  const tzOffset = dateObj.getTimezoneOffset() * 60000;
  const localISOTime = (new Date(dateObj - tzOffset)).toISOString().slice(0, -1).substring(0, 16);
  dateInput.value = localISOTime;
});

saveBtn.addEventListener('click', () => {
  sfx.click();
  const newLabel = labelInput.value.trim() || 'NEXT MILESTONE';
  const newDate = Date.parse(dateInput.value);
  
  if (!isNaN(newDate)) {
    setCountdownTarget(newDate, newLabel);
    settingsPanel.classList.add('hidden');
    speak(`Countdown target modified, BOSS.`);
  } else {
    sfx.error();
    alert('Please select a valid date/time');
  }
});

cancelBtn.addEventListener('click', () => {
  sfx.click();
  settingsPanel.classList.add('hidden');
});

setInterval(updateCountdown, 1000);
updateCountdown();


// WIDGET LOGIC: COUNTDOWN TIMER
let timerInterval;
let timerTimeLeft = 300;
let timerTotalDuration = 300;
let timerState = 'stopped';

const timerDisplay = document.getElementById('timer-display');
const timerProgress = document.getElementById('timer-progress');
const timerStartBtn = document.getElementById('timer-start-btn');
const timerPauseBtn = document.getElementById('timer-pause-btn');
const timerResetBtn = document.getElementById('timer-reset-btn');
const timerSetupInputs = document.getElementById('timer-setup-inputs');
const minInput = document.getElementById('timer-min-input');
const secInput = document.getElementById('timer-sec-input');

const ringRadius = 50;
const ringCircumference = 2 * Math.PI * ringRadius;

function updateTimerDisplay() {
  const m = Math.floor(timerTimeLeft / 60);
  const s = timerTimeLeft % 60;
  timerDisplay.textContent = `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  
  const progressRatio = timerTimeLeft / timerTotalDuration;
  const offset = ringCircumference - (progressRatio * ringCircumference);
  timerProgress.style.strokeDashoffset = offset;
}

function startTimer(duration = null) {
  if (timerState === 'running') return;
  
  if (duration !== null) {
    timerTimeLeft = duration;
    timerTotalDuration = duration;
  } else if (timerState === 'stopped') {
    const mins = parseInt(minInput.value, 10) || 0;
    const secs = parseInt(secInput.value, 10) || 0;
    timerTimeLeft = (mins * 60) + secs;
    timerTotalDuration = timerTimeLeft;
  }
  
  if (timerTimeLeft <= 0) return;
  
  timerState = 'running';
  timerSetupInputs.classList.add('hidden');
  timerStartBtn.classList.add('hidden');
  timerPauseBtn.classList.remove('hidden');
  
  updateTimerDisplay();
  
  timerInterval = setInterval(() => {
    timerTimeLeft--;
    updateTimerDisplay();
    
    if (timerTimeLeft <= 0) {
      clearInterval(timerInterval);
      timerState = 'stopped';
      timerSetupInputs.classList.remove('hidden');
      timerStartBtn.classList.remove('hidden');
      timerPauseBtn.classList.add('hidden');
      
      sfx.alert();
      speak("Timer complete, BOSS.");
      
      const orig = assistantCoreContainer.style.background;
      let flashes = 0;
      const flashInt = setInterval(() => {
        assistantCoreContainer.style.background = flashes % 2 === 0 ? 'rgba(239, 68, 68, 0.4)' : orig;
        flashes++;
        if (flashes >= 6) {
          clearInterval(flashInt);
          assistantCoreContainer.style.background = '';
        }
      }, 300);
    }
  }, 1000);
}

function pauseTimer() {
  if (timerState !== 'running') return;
  clearInterval(timerInterval);
  timerState = 'paused';
  timerStartBtn.classList.remove('hidden');
  timerPauseBtn.classList.add('hidden');
}

function resetTimer() {
  clearInterval(timerInterval);
  timerState = 'stopped';
  timerSetupInputs.classList.remove('hidden');
  timerStartBtn.classList.remove('hidden');
  timerPauseBtn.classList.add('hidden');
  
  const mins = parseInt(minInput.value, 10) || 0;
  const secs = parseInt(secInput.value, 10) || 0;
  timerTimeLeft = (mins * 60) + secs;
  timerTotalDuration = timerTimeLeft || 300;
  updateTimerDisplay();
}

timerStartBtn.addEventListener('click', () => { sfx.click(); startTimer(); });
timerPauseBtn.addEventListener('click', () => { sfx.click(); pauseTimer(); });
timerResetBtn.addEventListener('click', () => { sfx.click(); resetTimer(); });


// WIDGET LOGIC: STOPWATCH CHRONOMETER
let stopwatchInterval;
let stopwatchTime = 0;
let stopwatchState = 'stopped';
let laps = [];

const swDisplay = document.getElementById('sw-display');
const swStartBtn = document.getElementById('sw-start-btn');
const swStopBtn = document.getElementById('sw-stop-btn');
const swResetBtn = document.getElementById('sw-reset-btn');
const swLapBtn = document.getElementById('sw-lap-btn');
const swLapsList = document.getElementById('sw-laps');

function updateStopwatchDisplay() {
  const totalSecs = Math.floor(stopwatchTime / 1000);
  const ms = Math.floor((stopwatchTime % 1000) / 10);
  const s = totalSecs % 60;
  const m = Math.floor(totalSecs / 60);
  
  swDisplay.innerHTML = `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}<span class="ms">.${String(ms).padStart(2, '0')}</span>`;
}

function startStopwatch() {
  if (stopwatchState === 'running') return;
  stopwatchState = 'running';
  swStartBtn.classList.add('hidden');
  swStopBtn.classList.remove('hidden');
  swLapBtn.disabled = false;
  
  const startTime = Date.now() - stopwatchTime;
  stopwatchInterval = setInterval(() => {
    stopwatchTime = Date.now() - startTime;
    updateStopwatchDisplay();
  }, 10);
}

function stopStopwatch() {
  if (stopwatchState !== 'running') return;
  clearInterval(stopwatchInterval);
  stopwatchState = 'stopped';
  swStartBtn.classList.remove('hidden');
  swStopBtn.classList.add('hidden');
  swLapBtn.disabled = true;
}

function resetStopwatch() {
  clearInterval(stopwatchInterval);
  stopwatchState = 'stopped';
  stopwatchTime = 0;
  laps = [];
  swStartBtn.classList.remove('hidden');
  swStopBtn.classList.add('hidden');
  swLapBtn.disabled = true;
  updateStopwatchDisplay();
  swLapsList.innerHTML = '';
}

function lapStopwatch() {
  if (stopwatchState !== 'running') return;
  
  const totalSecs = Math.floor(stopwatchTime / 1000);
  const ms = Math.floor((stopwatchTime % 1000) / 10);
  const s = totalSecs % 60;
  const m = Math.floor(totalSecs / 60);
  const lapTimeStr = `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}.${String(ms).padStart(2, '0')}`;
  
  laps.push(lapTimeStr);
  
  const lapDiv = document.createElement('div');
  lapDiv.className = 'lap-item';
  lapDiv.innerHTML = `
    <span class="lap-number">LAP ${laps.length}</span>
    <span class="lap-time">${lapTimeStr}</span>
  `;
  
  swLapsList.insertBefore(lapDiv, swLapsList.firstChild);
}

swStartBtn.addEventListener('click', () => { sfx.click(); startStopwatch(); });
swStopBtn.addEventListener('click', () => { sfx.click(); stopStopwatch(); });
swResetBtn.addEventListener('click', () => { sfx.click(); resetStopwatch(); });
swLapBtn.addEventListener('click', () => { sfx.click(); lapStopwatch(); });


// SYSTEM: METADATA & UPTIME MONITOR
const sysUptimeVal = document.getElementById('system-uptime');
const sysBatteryVal = document.getElementById('system-battery');
const hudClock = document.getElementById('hud-clock');
const sysPing = document.getElementById('sys-ping');

function updateClock() {
  const d = new Date();
  hudClock.textContent = d.toLocaleTimeString([], { hour12: false });
}

async function fetchSystemDiagnostics() {
  try {
    const start = Date.now();
    const response = await fetch('/api/system');
    const latency = Date.now() - start;
    sysPing.textContent = `${latency}ms`;
    
    const data = await response.json();
    if (data.success) {
      if (data.data.battery !== 'Unknown') {
        sysBatteryVal.textContent = `${data.data.battery.percent}% (${data.data.battery.state})`;
        if (data.data.battery.percent < 20) {
          sysBatteryVal.style.color = 'var(--neon-pink)';
        }
      }
      
      // Update real CPU and RAM gauges in HUD status bar
      document.getElementById('hud-cpu-bar').style.width = `${data.data.cpu}%`;
      document.getElementById('hud-cpu-val').textContent = `${data.data.cpu}%`;
      document.getElementById('hud-ram-bar').style.width = `${data.data.ram}%`;
      document.getElementById('hud-ram-val').textContent = `${data.data.ram}%`;
      
      // Update Memory Card visual stat
      document.querySelector('.sys-stat:nth-child(2) .val').textContent = `${data.data.ram}%`;
      logToMind(`[OS Diagnostics] Host CPU Load: ${data.data.cpu}% | Memory Load: ${data.data.ram}%`);
    }
  } catch (err) {
    sysPing.textContent = 'Offline';
    if (navigator.getBattery) {
      navigator.getBattery().then(bat => {
        sysBatteryVal.textContent = `${Math.floor(bat.level * 100)}% ${bat.charging ? '(charging)' : ''}`;
      });
    }
  }
}

// Increment Uptime Counter
setInterval(() => {
  systemUptimeSeconds++;
  const hrs = Math.floor(systemUptimeSeconds / 3600);
  const mins = Math.floor((systemUptimeSeconds % 3600) / 60);
  const secs = systemUptimeSeconds % 60;
  sysUptimeVal.textContent = `${String(hrs).padStart(2, '0')}:${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}, 1000);

setInterval(updateClock, 1000);
setInterval(fetchSystemDiagnostics, 10000);

updateClock();
fetchSystemDiagnostics();


// SPATIAL 3D CARD PERSPECTIVE TILT
const panels = document.querySelectorAll('.widget-panel, .assistant-core-container');
panels.forEach(panel => {
  panel.addEventListener('mousemove', (e) => {
    const rect = panel.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    
    const centerX = rect.width / 2;
    const centerY = rect.height / 2;
    
    const tiltX = (centerY - y) / centerY * 5;
    const tiltY = (x - centerX) / centerX * 5;
    
    panel.style.transform = `perspective(1000px) rotateX(${tiltX}deg) rotateY(${tiltY}deg) scale3d(1.01, 1.01, 1.01)`;
  });
  
  panel.addEventListener('mouseleave', () => {
    panel.style.transform = '';
  });
});

// ONBOARDING TUTORIAL LOGIC
let currentTutorialStepVal = 1;
const maxTutorialSteps = 4;

window.nextTutorialStep = function() {
  sfx.confirm();
  if (currentTutorialStepVal < maxTutorialSteps) {
    document.querySelector(`.tutorial-step[data-step="${currentTutorialStepVal}"]`).classList.remove('active');
    currentTutorialStepVal++;
    document.querySelector(`.tutorial-step[data-step="${currentTutorialStepVal}"]`).classList.add('active');
    document.getElementById('tutorial-step-indicator').textContent = `STEP ${currentTutorialStepVal}/4`;
  }
};

window.prevTutorialStep = function() {
  sfx.click();
  if (currentTutorialStepVal > 1) {
    document.querySelector(`.tutorial-step[data-step="${currentTutorialStepVal}"]`).classList.remove('active');
    currentTutorialStepVal--;
    document.querySelector(`.tutorial-step[data-step="${currentTutorialStepVal}"]`).classList.add('active');
    document.getElementById('tutorial-step-indicator').textContent = `STEP ${currentTutorialStepVal}/4`;
  }
};

window.finishTutorial = function() {
  sfx.confirm();
  speak("Onboarding sequence completed, BOSS. Systems fully functional.");
  document.getElementById('widget-tutorial').style.display = 'none';
  localStorage.setItem('friday_tutorial_finished', 'true');
};

// Initialization Greeting
window.addEventListener('DOMContentLoaded', () => {
  canvas = document.getElementById('waveform-canvas');
  if (canvas) {
    ctx = canvas.getContext('2d');
  }
  setCoreState('idle');
  logToConsole("All systems nominal, BOSS.", "success");
  logToMind("[Agent Init] Voice synthesizers and recognition grammar models loaded.");
  
  if (localStorage.getItem('friday_tutorial_finished') === 'true') {
    document.getElementById('widget-tutorial').style.display = 'none';
  }

  // Welcome Overlay click logic
  const welcomeOverlay = document.getElementById('pre-dashboard-overlay');
  if (welcomeOverlay) {
    // Transition from cinematic intro to interactive mode after 3 seconds
    setTimeout(() => {
      const introSeq = welcomeOverlay.querySelector('.intro-sequence');
      const interactiveEl = welcomeOverlay.querySelector('.welcome-interactive-elements');
      
      if (introSeq && interactiveEl) {
        introSeq.style.transition = 'opacity 0.5s ease';
        introSeq.style.opacity = '0';
        setTimeout(() => {
          introSeq.classList.add('hidden');
          interactiveEl.classList.remove('hidden');
          setTimeout(() => {
            interactiveEl.classList.add('show');
            welcomeOverlay.classList.remove('intro-mode'); // Enable click-to-start
          }, 50);
        }, 500);
      }
    }, 3000);

    let isBooting = false;
    welcomeOverlay.addEventListener('click', () => {
      if (isBooting) return;
      isBooting = true;
      welcomeOverlay.style.pointerEvents = 'none'; // Disable double-clicking bugs
      
      if (audioCtx.state === 'suspended') {
        audioCtx.resume();
      }
      
      // Initialize dynamic core radial visualizer loop
      initPermanentCoreVisualizer();
      
      playIntroMusic();
      
      // Update welcome instruction
      const welcomeInst = document.querySelector('.welcome-instruction');
      if (welcomeInst) {
        welcomeInst.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> RUNNING SYSTEM INITIALIZATION SEQUENCES...';
      }

      // Update logs in real-time to match accelerated boot chime
      const logsContainer = document.querySelector('.welcome-boot-logs');
      if (logsContainer) {
        logsContainer.innerHTML = `
          <div class="boot-line"><span class="success">[ OK ]</span> AUTHORIZATION SIGNATURE ACCEPTED.</div>
          <div class="boot-line"><span class="loading">[ RUN ]</span> WAKING NEURAL CORE INTERFACE...</div>
        `;
        
        setTimeout(() => {
          logsContainer.innerHTML += `<div class="boot-line"><span class="success">[ OK ]</span> CORE COGNITIVE SYNAPSE CHANNELS ACTIVE.</div>`;
          logsContainer.innerHTML += `<div class="boot-line"><span class="loading">[ RUN ]</span> COMPILING AUDIO CHANNELS & MEMORY PIPES...</div>`;
        }, 500);

        setTimeout(() => {
          logsContainer.innerHTML += `<div class="boot-line"><span class="success">[ OK ]</span> ACOUSTIC TRANSLATION CHANNELS ONLINE.</div>`;
          logsContainer.innerHTML += `<div class="boot-line"><span class="loading">[ RUN ]</span> SYNCHRONIZING WITH macOS BRIDGE PIPES...</div>`;
        }, 1000);

        setTimeout(() => {
          logsContainer.innerHTML += `<div class="boot-line"><span class="success">[ OK ]</span> LINK ESTABLISHED. ALL SYSTEMS NOMINAL.</div>`;
          logsContainer.innerHTML += `<div class="boot-line"><span class="success" style="color: var(--neon-cyan)">[ READY ] FRIDAY CORE ACTIVE</span></div>`;
        }, 1500);
      }

      // Visual transition after music completes (at 2s)
      setTimeout(() => {
        welcomeOverlay.classList.add('fade-out');
      }, 2000);
      
      // Greet BOSS with First-Time-of-the-Day awareness (at 2.3s)
      setTimeout(() => {
        const greetingText = "Hi, I am Jenny, your neural assistant. All systems are online and fully operational. How can I help you today, BOSS?";

        speak(greetingText);
        logToConsole(greetingText, "success");
        logToMind("[Daily Initialization] " + greetingText);
        setCoreState('idle');
      }, 2300);
      
      setTimeout(() => {
        welcomeOverlay.remove();
      }, 2800);
    });
  }

  // Siri HUD Overlay Controller & Quick Command Executor
  window.toggleSiriHud = function(show) {
    const siriCard = document.getElementById('siri-hud-card');
    if (!siriCard) return;

    if (show === undefined) {
      show = siriCard.classList.contains('hidden');
    }

    if (show) {
      siriCard.classList.remove('hidden');
      sfx.confirm();
      if (!isListening) {
        window.toggleJennyDirectListening(true);
      }
    } else {
      siriCard.classList.add('hidden');
      sfx.click();
    }
  };

  window.executeQuickCommand = function(cmdStr) {
    const promptTitle = document.getElementById('siri-prompt-title');
    const transPreview = document.getElementById('siri-transcript-preview');
    if (promptTitle) promptTitle.textContent = `Executing: "${cmdStr}"`;
    if (transPreview) transPreview.textContent = `Processing Siri / Jenny command...`;
    
    window.toggleSiriHud(true);
    handleCommand(cmdStr);
  };

  // Direct Mic Toggle function for Menubar, Siri HUD & Floating Overlay
  window.toggleJennyDirectListening = function(forceStart) {
    sfx.confirm();
    isPassiveWakeWordActive = false; // Direct Mic Mode!

    const floatState = document.getElementById('floating-mic-state');
    const menubarState = document.getElementById('menubar-mic-status');
    const siriDot = document.getElementById('siri-status-dot');
    const siriBadge = document.getElementById('siri-badge-text');
    const siriPrompt = document.getElementById('siri-prompt-title');
    const siriPreview = document.getElementById('siri-transcript-preview');

    if (isListening && !forceStart) {
      safeStopRecognition();
      if (floatState) floatState.textContent = 'READY (CLICK TO SPEAK)';
      if (menubarState) menubarState.innerHTML = '<i class="fa-solid fa-microphone"></i> SPEAK TO JENNY';
      if (siriDot) siriDot.classList.remove('listening');
      if (siriBadge) siriBadge.textContent = 'SIRI / JENNY NEURAL LINK';
      if (siriPrompt) siriPrompt.textContent = "Mic Paused";
      if (siriPreview) siriPreview.textContent = "Tap glowing Siri sphere or menu bar icon to activate...";
      logToConsole("Microphone paused, BOSS.", "system");
    } else {
      if (floatState) floatState.textContent = 'LISTENING...';
      if (menubarState) menubarState.innerHTML = '<i class="fa-solid fa-microphone"></i> LISTENING...';
      if (siriDot) siriDot.classList.add('listening');
      if (siriBadge) siriBadge.textContent = 'SIRI / JENNY LISTENING...';
      if (siriPrompt) siriPrompt.textContent = "Listening...";
      if (siriPreview) siriPreview.textContent = "Speak your command clearly, BOSS...";
      
      const siriCard = document.getElementById('siri-hud-card');
      if (siriCard && siriCard.classList.contains('hidden')) {
        siriCard.classList.remove('hidden');
      }

      logToConsole("Jenny listening for your vocal input, BOSS...", "success");
      safeStartRecognition();
    }
  };

  // Siri Dynamic Wave Canvas Visualizer (60FPS Ribbon Waves)
  function initSiriWaveAnimation() {
    const canvas = document.getElementById('siri-wave-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let step = 0;

    function animate() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      step += 0.06;

      const isVoiceActive = isListening || isSpeaking;
      const amplitude = isVoiceActive ? 14 : 3;
      const colors = [
        'rgba(0, 242, 254, 0.85)',
        'rgba(255, 0, 127, 0.85)',
        'rgba(121, 40, 202, 0.85)',
        'rgba(255, 0, 212, 0.85)'
      ];

      colors.forEach((color, idx) => {
        ctx.beginPath();
        ctx.lineWidth = isVoiceActive ? 2.2 : 1.2;
        ctx.strokeStyle = color;

        for (let x = 0; x < canvas.width; x += 4) {
          const freq = 0.03 + idx * 0.005;
          const y = canvas.height / 2 + Math.sin(x * freq + step + idx * 1.5) * amplitude * Math.sin((x / canvas.width) * Math.PI);
          if (x === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        ctx.stroke();
      });

      requestAnimationFrame(animate);
    }
    animate();
  }
  initSiriWaveAnimation();

  // Voice Mute/Unmute Toggle logic
  const voiceMuteBtn = document.getElementById('voice-mute-btn');
  const voiceMuteStatus = document.getElementById('voice-mute-status');
  if (voiceMuteBtn) {
    voiceMuteBtn.addEventListener('click', () => {
      isVoiceMuted = !isVoiceMuted;
      sfx.click();
      if (isVoiceMuted) {
        voiceMuteStatus.innerHTML = '<i class="fa-solid fa-volume-xmark"></i> MUTED';
        voiceMuteStatus.classList.remove('active');
        voiceMuteStatus.classList.add('muted');
        logToConsole("Voice feedback muted, BOSS.", "system");
        logToMind("[Vocal Engine] Output stream disabled by host override.");
        if (synth.speaking) {
          synth.cancel();
        }
      } else {
        voiceMuteStatus.innerHTML = '<i class="fa-solid fa-volume-high"></i> ACTIVE';
        voiceMuteStatus.classList.remove('muted');
        voiceMuteStatus.classList.add('active');
        logToConsole("Voice feedback active, BOSS.", "success");
        logToMind("[Vocal Engine] Output stream enabled.");
        speak("Voice active, BOSS.");
      }
    });
  }
  
  let permanentMicStream = null;
  permanentAnalyser = null;
  let lastClapTime = 0;
  const CLAP_THRESHOLD = 0.38;
  const MIN_CLAP_INTERVAL = 220;
  const MAX_DOUBLE_CLAP_GAP = 900;

  async function initPermanentAudioStream() {
    try {
      if (audioCtx.state === 'suspended') {
        await audioCtx.resume();
      }
      
      permanentMicStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      permanentAnalyser = audioCtx.createAnalyser();
      permanentAnalyser.fftSize = 256;
      const source = audioCtx.createMediaStreamSource(permanentMicStream);
      source.connect(permanentAnalyser);
      
      startClapDetectionLoop();
      logToMind("[Acoustic Engine] Background clap detection thread active.");
    } catch (err) {
      console.error("Failed to initialize background audio stream for claps:", err);
    }
  }

  function startClapDetectionLoop() {
    if (!permanentAnalyser) return;
    
    const bufferLength = permanentAnalyser.frequencyBinCount;
    const dataArray = new Float32Array(bufferLength);
    
    function checkAudio() {
      requestAnimationFrame(checkAudio);
      
      if (isSpeaking) return;
      
      permanentAnalyser.getFloatTimeDomainData(dataArray);
      let sum = 0;
      for (let i = 0; i < bufferLength; i++) {
        sum += dataArray[i] * dataArray[i];
      }
      const rms = Math.sqrt(sum / bufferLength);
      
      if (rms > CLAP_THRESHOLD) {
        const now = Date.now();
        if (now - lastClapTime > MIN_CLAP_INTERVAL) {
          const gap = now - lastClapTime;
          if (gap > 250 && gap < MAX_DOUBLE_CLAP_GAP) {
            logToConsole("Double clap detected! Initializing vocal interface...", "system");
            logToMind("[Acoustic Engine] Double clap signature match. Waking system.");
            wakeUpJenny();
            lastClapTime = 0;
          } else {
            lastClapTime = now;
          }
        }
      }
    }
    
    checkAudio();
  }

  function wakeUpJenny() {
    sfx.confirm();
    isPassiveWakeWordActive = false;
    
    if (isListening) {
      safeStopRecognition();
    }
    
    speak("Hi I am Jenny, your neural assistant. How can I help you today, BOSS?");
    
    setTimeout(() => {
      if (!isSpeaking && !isListening && recognition) {
        try {
          recognition.start();
        } catch (e) {
          console.error("Error starting recognition on wake:", e);
        }
      }
    }, 2200);
  }

  function initBackgroundNetwork() {
    const canvas = document.getElementById('bg-network-canvas');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    let width = canvas.width = window.innerWidth;
    let height = canvas.height = window.innerHeight;
    
    const particles = [];
    const particleCount = 75;
    const connectionDistance = 140;
    
    window.addEventListener('resize', () => {
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
    });
    
    class Particle {
      constructor() {
        this.x = Math.random() * width;
        this.y = Math.random() * height;
        this.vx = (Math.random() - 0.5) * 0.4;
        this.vy = (Math.random() - 0.5) * 0.4;
        this.radius = Math.random() * 2 + 1;
      }
      
      update() {
        this.x += this.vx;
        this.y += this.vy;
        
        if (this.x < 0 || this.x > width) this.vx *= -1;
        if (this.y < 0 || this.y > height) this.vy *= -1;
      }
      
      draw() {
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(6, 182, 212, 0.25)';
        ctx.fill();
      }
    }
    
    for (let i = 0; i < particleCount; i++) {
      particles.push(new Particle());
    }
    
    let mouse = { x: null, y: null };
    window.addEventListener('mousemove', (e) => {
      mouse.x = e.clientX;
      mouse.y = e.clientY;
    });
    window.addEventListener('mouseleave', () => {
      mouse.x = null;
      mouse.y = null;
    });
    
    function animate() {
      requestAnimationFrame(animate);
      ctx.clearRect(0, 0, width, height);
      
      // Draw connections
      for (let i = 0; i < particles.length; i++) {
        particles[i].update();
        particles[i].draw();
        
        for (let j = i + 1; j < particles.length; j++) {
          const dx = particles[i].x - particles[j].x;
          const dy = particles[i].y - particles[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          
          if (dist < connectionDistance) {
            const alpha = (1 - dist / connectionDistance) * 0.12;
            ctx.strokeStyle = `rgba(168, 85, 247, ${alpha})`;
            ctx.lineWidth = 0.5;
            ctx.beginPath();
            ctx.moveTo(particles[i].x, particles[i].y);
            ctx.lineTo(particles[j].x, particles[j].y);
            ctx.stroke();
          }
        }
        
        // Mouse connections
        if (mouse.x !== null) {
          const dx = particles[i].x - mouse.x;
          const dy = particles[i].y - mouse.y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 180) {
            const alpha = (1 - dist / 180) * 0.15;
            ctx.strokeStyle = `rgba(6, 182, 212, ${alpha})`;
            ctx.lineWidth = 0.6;
            ctx.beginPath();
            ctx.moveTo(particles[i].x, particles[i].y);
            ctx.lineTo(mouse.x, mouse.y);
            ctx.stroke();
          }
        }
      }
    }
    
    animate();
  }

  // Initialize Particle Network Background
  initBackgroundNetwork();

  setTimeout(() => {
    if (audioCtx.state === 'suspended') {
      logToConsole("Interactivity audio suspended. Click core to initialize sound systems.", "system");
    }
  }, 1000);
});

window.sendQuickCommand = function(cmd) {
  const terminalInput = document.getElementById('terminal-input');
  if (terminalInput) {
    terminalInput.value = cmd;
    handleCommand(cmd);
  }
};

// PROJECT PROGRESSION MATRIX ENGINE
let projectMilestones = JSON.parse(localStorage.getItem('friday_project_milestones')) || [
  { title: "Phase 1: Core Neural Acoustic Engine", completed: true },
  { title: "Phase 2: macOS Native IPC Controls & Security", completed: true },
  { title: "Phase 3: High-Tech Glassmorphic UI Overhaul", completed: true },
  { title: "Phase 4: Autonomous Agent Pipeline Integrations", completed: false }
];

function renderMilestones() {
  const container = document.getElementById('milestones-list');
  if (!container) return;
  
  const completedCount = projectMilestones.filter(m => m.completed).length;
  const pct = Math.round((completedCount / (projectMilestones.length || 1)) * 100);
  
  const pctBadge = document.getElementById('project-overall-pct');
  const pctText = document.getElementById('project-bar-pct-text');
  const pctFill = document.getElementById('project-bar-fill');
  
  if (pctBadge) pctBadge.textContent = `${pct}% COMPLETE`;
  if (pctText) pctText.textContent = `${pct}%`;
  if (pctFill) pctFill.style.width = `${pct}%`;
  
  container.innerHTML = '';
  projectMilestones.forEach((m, idx) => {
    const div = document.createElement('div');
    div.className = `milestone-item ${m.completed ? 'completed' : 'pending'}`;
    div.innerHTML = `
      <i class="fa-solid ${m.completed ? 'fa-circle-check' : 'fa-circle'}"></i>
      <span class="title" style="flex:1;">${m.title}</span>
      <button class="milestone-del-btn" onclick="deleteMilestone(${idx}); event.stopPropagation();"><i class="fa-solid fa-trash"></i></button>
    `;
    div.onclick = () => toggleMilestone(idx);
    container.appendChild(div);
  });
  
  localStorage.setItem('friday_project_milestones', JSON.stringify(projectMilestones));
}

window.toggleMilestone = function(idx) {
  if (projectMilestones[idx]) {
    projectMilestones[idx].completed = !projectMilestones[idx].completed;
    renderMilestones();
  }
};

window.deleteMilestone = function(idx) {
  projectMilestones.splice(idx, 1);
  renderMilestones();
};

window.addMilestoneFromInput = function() {
  const input = document.getElementById('milestone-input');
  if (input && input.value.trim()) {
    projectMilestones.push({ title: input.value.trim(), completed: false });
    input.value = '';
    renderMilestones();
  }
};

// Poll Native OS Menubar / Tray Mic Toggle Bridge
let lastHandledNativeToggle = 0;
async function pollNativeMicBridge() {
  try {
    const res = await fetch('/api/toggle-mic-poll');
    const data = await res.json();
    if (data.success && data.lastToggle > lastHandledNativeToggle && lastHandledNativeToggle !== 0) {
      lastHandledNativeToggle = data.lastToggle;
      toggleJennyDirectListening();
    } else if (lastHandledNativeToggle === 0 && data.lastToggle) {
      lastHandledNativeToggle = data.lastToggle;
    }
  } catch (e) {}
}
setInterval(pollNativeMicBridge, 1000);

// Poll Google AI Studio Token & Quota Metrics
async function pollGeminiQuota() {
  try {
    const res = await fetch('/api/gemini-quota');
    const data = await res.json();
    if (data.success) {
      const rpmText = document.getElementById('quota-rpm-text');
      const rpmFill = document.getElementById('quota-rpm-fill');
      const tpmText = document.getElementById('quota-tpm-text');
      const tpmFill = document.getElementById('quota-tpm-fill');
      const rpdText = document.getElementById('quota-rpd-text');
      const rpdFill = document.getElementById('quota-rpd-fill');
      const badge = document.getElementById('quota-status-badge');

      if (rpmText) rpmText.textContent = `${data.rpm.current} / ${data.rpm.max} RPM`;
      if (rpmFill) rpmFill.style.width = `${Math.round((data.rpm.current / data.rpm.max) * 100)}%`;

      if (tpmText) tpmText.textContent = `${data.tpm.current.toLocaleString()} / ${data.tpm.max.toLocaleString()} TPM`;
      if (tpmFill) tpmFill.style.width = `${Math.round((data.tpm.current / data.tpm.max) * 100)}%`;

      if (rpdText) rpdText.textContent = `${data.rpd.current} / ${data.rpd.max} RPD`;
      if (rpdFill) rpdFill.style.width = `${Math.round((data.rpd.current / data.rpd.max) * 100)}%`;

      if (badge) badge.textContent = data.status;
    }
  } catch (e) {}
}
setInterval(pollGeminiQuota, 5000);

window.saveGeminiKeyFromInput = function() {
  const input = document.getElementById('gemini-key-input');
  if (input && input.value.trim()) {
    localStorage.setItem('gemini_api_key', input.value.trim());
    sfx.confirm();
    speak("Google AI Studio API Key saved, BOSS.");
    logToConsole("Google AI Studio API Key registered into local memory.", "success");
    input.value = '';
    pollGeminiQuota();
  }
};

// 60FPS HARDWARE TELEMETRY OSCILLOSCOPE ENGINE
const cpuHistory = new Array(50).fill(15);
const ramHistory = new Array(50).fill(45);

function initTelemetryOscilloscope() {
  const canvas = document.getElementById('telemetry-oscilloscope-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  
  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
    ctx.lineWidth = 1;
    for (let x = 0; x < canvas.width; x += 40) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, canvas.height);
      ctx.stroke();
    }
    for (let y = 0; y < canvas.height; y += 25) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(canvas.width, y);
      ctx.stroke();
    }

    ctx.beginPath();
    ctx.strokeStyle = '#10b981';
    ctx.lineWidth = 2;
    ctx.shadowColor = '#10b981';
    ctx.shadowBlur = 8;
    const stepX = canvas.width / (ramHistory.length - 1);
    ramHistory.forEach((val, i) => {
      const y = canvas.height - (val / 100) * (canvas.height - 20) - 10;
      if (i === 0) ctx.moveTo(0, y);
      else ctx.lineTo(i * stepX, y);
    });
    ctx.stroke();

    ctx.beginPath();
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 2;
    ctx.shadowColor = '#ffffff';
    ctx.shadowBlur = 10;
    cpuHistory.forEach((val, i) => {
      const y = canvas.height - (val / 100) * (canvas.height - 20) - 10;
      if (i === 0) ctx.moveTo(0, y);
      else ctx.lineTo(i * stepX, y);
    });
    ctx.stroke();
    ctx.shadowBlur = 0;

    requestAnimationFrame(draw);
  }

  draw();
}

async function updateTelemetryData() {
  try {
    const res = await fetch('/api/system-status');
    const data = await res.json();
    if (data.success) {
      cpuHistory.push(data.cpu.usage);
      if (cpuHistory.length > 50) cpuHistory.shift();

      ramHistory.push(data.ram.usage);
      if (ramHistory.length > 50) ramHistory.shift();

      const cpuText = document.getElementById('telemetry-cpu-val');
      const ramText = document.getElementById('telemetry-ram-val');
      const diskText = document.getElementById('telemetry-disk-val');

      if (cpuText) cpuText.textContent = `${data.cpu.usage}%`;
      if (ramText) ramText.textContent = `${data.ram.usage}%`;
      if (diskText) diskText.textContent = `${data.disk.free}`;
    }
  } catch (e) {}
}

setInterval(updateTelemetryData, 1000);

// ATMOSPHERIC WEATHER RADAR ENGINE
async function fetchWeatherRadar() {
  try {
    const res = await fetch('/api/weather');
    const data = await res.json();
    if (data.success) {
      const tempVal = document.getElementById('weather-temp-val');
      const condVal = document.getElementById('weather-condition-val');
      const cityBadge = document.getElementById('weather-city-badge');
      const humidityVal = document.getElementById('weather-humidity-val');
      const windVal = document.getElementById('weather-wind-val');
      const iconBox = document.getElementById('weather-icon-box');

      if (tempVal) tempVal.textContent = `${data.tempC}°C`;
      if (condVal) condVal.textContent = data.condition;
      if (cityBadge) cityBadge.textContent = data.city.toUpperCase();
      if (humidityVal) humidityVal.textContent = `${data.humidity}%`;
      if (windVal) windVal.textContent = `${data.windKmH} km/h`;

      if (iconBox) {
        if (data.type === 'rain') iconBox.innerHTML = '<i class="fa-solid fa-cloud-showers-heavy" style="color: #60a5fa;"></i>';
        else if (data.type === 'storm') iconBox.innerHTML = '<i class="fa-solid fa-cloud-bolt" style="color: #f59e0b;"></i>';
        else if (data.type === 'snow') iconBox.innerHTML = '<i class="fa-regular fa-snowflake" style="color: #93c5fd;"></i>';
        else iconBox.innerHTML = '<i class="fa-solid fa-cloud-sun" style="color: #fde047;"></i>';
      }
    }
  } catch (e) {}
}

setInterval(fetchWeatherRadar, 60000);

document.addEventListener('DOMContentLoaded', () => {
  renderMilestones();
  pollSystemTelemetry();
  initTelemetryOscilloscope();
  fetchWeatherRadar();
});

// SPATIAL FLOATING GLASS WINDOW OVERLAY MANAGER
let activeWindowWidgetId = null;
let activeWidgetOriginalParent = null;
let activeWidgetOriginalNextSibling = null;

window.openWidgetWindow = function(widgetId) {
  const widget = document.getElementById(widgetId);
  const overlay = document.getElementById('spatial-window-overlay');
  const body = document.getElementById('spatial-window-body');
  const title = document.getElementById('spatial-window-title');
  
  if (!widget || !overlay || !body) return;
  
  if (activeWindowWidgetId) {
    closeSpatialWindow(true);
  }
  
  activeWindowWidgetId = widgetId;
  activeWidgetOriginalParent = widget.parentNode;
  activeWidgetOriginalNextSibling = widget.nextSibling;
  
  const headerTitle = widget.querySelector('.header-title');
  if (title && headerTitle) {
    title.innerHTML = `<i class="fa-solid fa-up-right-from-square"></i> ${headerTitle.innerText}`;
  }
  
  body.appendChild(widget);
  widget.style.minHeight = '350px';
  
  overlay.classList.remove('hidden');
  sfx.confirm();
  logToMind(`[Spatial Manager] Popped out floating glass window: ${widgetId}`);
};

window.closeSpatialWindow = function(isSwitching = false) {
  const overlay = document.getElementById('spatial-window-overlay');
  
  if (!activeWindowWidgetId || !activeWidgetOriginalParent) {
    if (overlay) overlay.classList.add('hidden');
    return;
  }
  
  const widget = document.getElementById(activeWindowWidgetId);
  if (widget) {
    widget.style.minHeight = '';
    if (activeWidgetOriginalNextSibling) {
      activeWidgetOriginalParent.insertBefore(widget, activeWidgetOriginalNextSibling);
    } else {
      activeWidgetOriginalParent.appendChild(widget);
    }
  }
  
  activeWindowWidgetId = null;
  activeWidgetOriginalParent = null;
  activeWidgetOriginalNextSibling = null;
  
  if (!isSwitching && overlay) {
    overlay.classList.add('hidden');
    sfx.click();
    logToMind('[Spatial Manager] Spatial window closed.');
  }
};
