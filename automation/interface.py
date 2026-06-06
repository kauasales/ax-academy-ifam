import customtkinter as ctk
from tkinter import filedialog, messagebox, Text
from tkinterdnd2 import DND_FILES, TkinterDnD
import os
import threading
import webbrowser
from pathlib import Path
import sys
from datetime import datetime
from PIL import Image
import io
import base64

# Configurar tema moderno - fundo escuro
ctk.set_appearance_mode("dark")  # Modo escuro
ctk.set_default_color_theme("blue")  # Themes: "blue", "dark-blue", "green"

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from solucao_fretes import processar_transportadora, gerar_planilha_final

class FreteComparadorModerno(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        
        # Configuração da janela com fundo escuro
        self.title("🚚 Frete Comparador")
        self.geometry("900x700")
        self.configure(bg='#1a1a1a')  # Fundo escuro
        
        # Centralizar janela
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (900 // 2)
        y = (self.winfo_screenheight() // 2) - (700 // 2)
        self.geometry(f'900x700+{x}+{y}')
        
        # Variáveis
        self.arquivo_csv = None
        self.html_path = "comparativo_fretes.html"
        self.excel_path = "comparativo_fretes.xlsx"
        
        # Criar interface
        self.criar_interface()
        
    def criar_interface(self):
        """Criar interface moderna com fundo escuro"""
        
        # Frame principal com grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # Header com gradiente escuro
        header_frame = ctk.CTkFrame(self, height=120, corner_radius=0, fg_color="#2d2d2d")
        header_frame.grid(row=0, column=0, sticky="ew")
        header_frame.grid_propagate(False)
        
        # Título e ícone
        title_label = ctk.CTkLabel(
            header_frame, 
            text="🚚 Frete Comparador Pro", 
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color="#ffffff"
        )
        title_label.pack(pady=(30, 5))
        
        subtitle_label = ctk.CTkLabel(
            header_frame,
            text="Compare fretes entre Correios, Loggi e J&T Express",
            font=ctk.CTkFont(size=14),
            text_color="#d0d0d0"
        )
        subtitle_label.pack()
        
        # Frame principal de conteúdo - fundo escuro
        content_frame = ctk.CTkFrame(self, corner_radius=15, fg_color="#1e1e1e")
        content_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=20)
        content_frame.grid_columnconfigure(0, weight=1)
        
        # Área de upload com drag & drop
        upload_frame = ctk.CTkFrame(content_frame, corner_radius=15, border_width=2, border_color="#3b8ed0", fg_color="#2d2d2d")
        upload_frame.grid(row=0, column=0, sticky="ew", pady=(0, 20), padx=20)
        upload_frame.grid_columnconfigure(0, weight=1)
        
        # Label de upload
        self.upload_label = ctk.CTkLabel(
            upload_frame,
            text="📁\nArraste e solte seu arquivo CSV aqui\nou clique para selecionar",
            font=ctk.CTkFont(size=16),
            text_color="#888888",
            height=150
        )
        self.upload_label.grid(row=0, column=0, padx=20, pady=20)
        
        # Configurar drag and drop
        upload_frame.drop_target_register(DND_FILES)
        upload_frame.dnd_bind('<<Drop>>', self.on_drop)
        self.upload_label.bind('<Button-1>', lambda e: self.selecionar_arquivo())
        upload_frame.bind('<Button-1>', lambda e: self.selecionar_arquivo())
        
        # Frame de informações do arquivo
        self.info_frame = ctk.CTkFrame(content_frame, corner_radius=10, fg_color="#2d2d2d")
        self.info_frame.grid(row=1, column=0, sticky="ew", pady=(0, 20), padx=20)
        self.info_frame.grid_columnconfigure(0, weight=1)
        
        self.file_info_label = ctk.CTkLabel(
            self.info_frame,
            text="Nenhum arquivo selecionado",
            font=ctk.CTkFont(size=13),
            text_color="#888888"
        )
        self.file_info_label.pack(pady=15)
        
        # Frame de progresso
        progress_frame = ctk.CTkFrame(content_frame, corner_radius=10, fg_color="#2d2d2d")
        progress_frame.grid(row=2, column=0, sticky="ew", pady=(0, 20), padx=20)
        progress_frame.grid_columnconfigure(0, weight=1)
        
        # Título do progresso
        progress_title = ctk.CTkLabel(
            progress_frame,
            text="📊 Progresso do Processamento",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#ffffff"
        )
        progress_title.pack(pady=(15, 10))
        
        # Status cards
        cards_frame = ctk.CTkFrame(progress_frame, fg_color="transparent")
        cards_frame.pack(fill="x", padx=20, pady=10)
        cards_frame.grid_columnconfigure((0,1,2), weight=1)
        
        # Card Correios
        self.card_correios = self.criar_card_status(cards_frame, "📮 Correios", 0)
        # Card Loggi
        self.card_loggi = self.criar_card_status(cards_frame, "🚚 Loggi", 1)
        # Card J&T
        self.card_jt = self.criar_card_status(cards_frame, "📦 J&T Express", 2)
        
        # Barra de progresso
        self.progress_bar = ctk.CTkProgressBar(progress_frame, height=15, corner_radius=7)
        self.progress_bar.pack(pady=(20, 15), padx=20)
        self.progress_bar.set(0)
        
        # Frame de ações
        actions_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        actions_frame.grid(row=3, column=0, sticky="ew", pady=(0, 20), padx=20)
        actions_frame.grid_columnconfigure((0,1), weight=1)
        
        self.processar_btn = ctk.CTkButton(
            actions_frame,
            text="🚀 Iniciar Processamento",
            command=self.iniciar_processamento,
            height=45,
            font=ctk.CTkFont(size=15, weight="bold"),
            corner_radius=10,
            state="disabled",
            fg_color="#3b8ed0",
            hover_color="#2c6ea8",
            text_color="#ffffff" 
        )
        self.processar_btn.grid(row=0, column=0, padx=5, sticky="ew")
        
        self.html_btn = ctk.CTkButton(
            actions_frame,
            text="🌐 Abrir Página",
            command=self.abrir_html,
            height=45,
            font=ctk.CTkFont(size=15, weight="bold"),
            corner_radius=10,
            state="disabled",
            fg_color="#2ecc71",
            hover_color="#27ae60",
            text_color="#ffffff" 
        )
        self.html_btn.grid(row=0, column=1, padx=5, sticky="ew")
        
        """
        # Frame de logs
        logs_frame = ctk.CTkFrame(content_frame, corner_radius=10, fg_color="#2d2d2d")
        logs_frame.grid(row=4, column=0, sticky="nsew", padx=20, pady=(0, 20))
        logs_frame.grid_columnconfigure(0, weight=1)
        logs_frame.grid_rowconfigure(1, weight=1)
        content_frame.grid_rowconfigure(4, weight=1)
        
        logs_title = ctk.CTkLabel(
            logs_frame,
            text="📝 Logs do Sistema",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#ffffff"
        )
        logs_title.pack(pady=(10, 5))
        
        # Usar Text widget nativo para logs coloridos
        self.log_text = Text(
            logs_frame, 
            height=10, 
            wrap="word",
            bg="#1e1e1e",
            fg="#ffffff",
            font=("Consolas", 10),
            relief="flat",
            padx=10,
            pady=10
        )
        self.log_text.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        # Configurar tags de cores para o log
        self.log_text.tag_config("info", foreground="#61afef")      # Azul para info
        self.log_text.tag_config("success", foreground="#98c379")   # Verde para sucesso
        self.log_text.tag_config("error", foreground="#e06c75")     # Vermelho para erro
        self.log_text.tag_config("warning", foreground="#e5c07b")   # Amarelo para warning
        self.log_text.tag_config("process", foreground="#56b6c2")   # Ciano para processamento
        
        # Scrollbar para o log
        scrollbar = ctk.CTkScrollbar(logs_frame, command=self.log_text.yview)
        scrollbar.pack(side="right", fill="y", padx=(0, 10), pady=(0, 10))
        self.log_text.config(yscrollcommand=scrollbar.set)
        """

    def criar_card_status(self, parent, titulo, coluna):
        """Criar card de status moderno com fundo escuro"""
        card = ctk.CTkFrame(parent, corner_radius=10, border_width=1, border_color="#3b8ed0", fg_color="#2d2d2d")
        card.grid(row=0, column=coluna, padx=5, sticky="ew")
        
        title = ctk.CTkLabel(card, text=titulo, font=ctk.CTkFont(size=14, weight="bold"), text_color="#ffffff")
        title.pack(pady=(10, 5))
        
        status_label = ctk.CTkLabel(
            card, 
            text="⏳ Aguardando", 
            font=ctk.CTkFont(size=12),
            text_color="#888888"
        )
        status_label.pack(pady=(0, 10))
        
        # Armazenar referências
        card.status_label = status_label
        card.titulo = titulo
        
        return card
    
    def atualizar_status_card(self, card, status, mensagem=None):
        """Atualizar status do card"""
        cores = {
            "processando": {"texto": "Processando...", "cor": "#f39c12"},
            "concluido": {"texto": "Concluído!", "cor": "#2ecc71"},
            "erro": {"texto": "Erro!", "cor": "#e74c3c"},
            "aguardando": {"texto": "Aguardando", "cor": "#888888"}
        }
        
        info = cores.get(status, cores["aguardando"])
        if mensagem:
            info["texto"] = mensagem
            
        card.status_label.configure(text=info["texto"], text_color=info["cor"])
        self.update_idletasks()
    
    def on_drop(self, event):
        """Manipular arquivo arrastado"""
        arquivo = event.data.strip('{}')
        self.carregar_arquivo(arquivo)
    
    def selecionar_arquivo(self):
        """Abrir diálogo para selecionar arquivo"""
        arquivo = filedialog.askopenfilename(
            title="Selecionar arquivo CSV",
            filetypes=[("Arquivos CSV", "*.csv"), ("Todos os arquivos", "*.*")]
        )
        if arquivo:
            self.carregar_arquivo(arquivo)
    
    def carregar_arquivo(self, arquivo):
        """Carregar e validar arquivo CSV"""
        if not os.path.exists(arquivo):
            messagebox.showerror("Erro", f"Arquivo não encontrado:\n{arquivo}")
            return
        
        if not arquivo.lower().endswith('.csv'):
            messagebox.showerror("Erro", "Por favor, selecione um arquivo CSV válido")
            return
        
        self.arquivo_csv = arquivo
        nome_arquivo = os.path.basename(arquivo)
        tamanho = os.path.getsize(arquivo)
        
        # Atualizar UI
        self.upload_label.configure(
            text=f"✅ {nome_arquivo}\n{self.formatar_tamanho(tamanho)}",
            text_color="#2ecc71"
        )
        self.file_info_label.configure(
            text=f"📄 Arquivo: {nome_arquivo}\n📏 Tamanho: {self.formatar_tamanho(tamanho)}",
            text_color="#2ecc71"
        )
        self.processar_btn.configure(state="normal")
        
        self.adicionar_log(f"Arquivo carregado: {nome_arquivo}", "success")
    
    def formatar_tamanho(self, bytes):
        """Formatar tamanho do arquivo"""
        for unidade in ['B', 'KB', 'MB', 'GB']:
            if bytes < 1024.0:
                return f"{bytes:.1f} {unidade}"
            bytes /= 1024.0
        return f"{bytes:.1f} GB"
    
    def adicionar_log(self, mensagem, tipo="info"):
        """Adicionar mensagem ao log com cores"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Mapear tipos para tags
        tag_map = {
            "info": "info",
            "success": "success",
            "erro": "error",
            "error": "error",
            "warning": "warning",
            "process": "process"
        }
        
        tag = tag_map.get(tipo, "info")
        
        # Inserir timestamp (cor neutra)
        #self.log_text.insert("end", f"[{timestamp}] ", "info")
        
        # Inserir mensagem com a cor específica
        #self.log_text.insert("end", f"{mensagem}\n", tag)
        
        # Rolar para o final
        #self.log_text.see("end")
        self.update_idletasks()
    
    def atualizar_progresso(self, valor, maximo=4):
        """Atualizar barra de progresso"""
        progresso = valor / maximo
        self.progress_bar.set(progresso)
        self.update_idletasks()
    
    def processar(self):
        """Processar os dados"""
        try:
            self.processar_btn.configure(state="disabled")
            self.atualizar_progresso(0)
            
            # Processar Correios
            self.atualizar_status_card(self.card_correios, "processando")
            self.adicionar_log("Processando Correios...", "process")
            resultados_correios = processar_transportadora(self.arquivo_csv, "correios")
            self.atualizar_status_card(self.card_correios, "concluido")
            self.adicionar_log("Correios processado com sucesso!", "success")
            self.atualizar_progresso(1)
            
            # Processar Loggi
            self.atualizar_status_card(self.card_loggi, "processando")
            self.adicionar_log("Processando Loggi...", "process")
            resultados_loggi = processar_transportadora(self.arquivo_csv, "loggi")
            self.atualizar_status_card(self.card_loggi, "concluido")
            self.adicionar_log("Loggi processado com sucesso!", "success")
            self.atualizar_progresso(2)
            
            # Processar J&T
            self.atualizar_status_card(self.card_jt, "processando")
            self.adicionar_log("Processando J&T Express...", "process")
            resultados_jt = processar_transportadora(self.arquivo_csv, "jt")
            self.atualizar_status_card(self.card_jt, "concluido")
            self.adicionar_log("J&T Express processado com sucesso!", "success")
            self.atualizar_progresso(3)
            
            # Gerar planilha final
            self.adicionar_log("Gerando planilha comparativa...", "process")
            gerar_planilha_final(resultados_correios, resultados_loggi, resultados_jt)
            self.adicionar_log("Planilha comparativa gerada com sucesso!", "success")
            self.atualizar_progresso(4)
            
            # Habilitar botão HTML
            self.html_btn.configure(state="normal")
            
            # Verificar arquivos
            if os.path.exists(self.html_path):
                self.adicionar_log(f"HTML gerado: {os.path.abspath(self.html_path)}", "success")
            if os.path.exists(self.excel_path):
                self.adicionar_log(f"Excel gerado: {os.path.abspath(self.excel_path)}", "success")
            
            messagebox.showinfo(
                "Sucesso!", 
                "Processamento concluído com sucesso!\n\nO arquivo HTML foi gerado."
            )
            
        except Exception as e:
            self.adicionar_log(f"ERRO: {str(e)}", "error")
            messagebox.showerror("Erro", f"Ocorreu um erro durante o processamento:\n\n{str(e)}")
            self.atualizar_status_card(self.card_correios, "erro")
            self.atualizar_status_card(self.card_loggi, "erro")
            self.atualizar_status_card(self.card_jt, "erro")
        finally:
            self.processar_btn.configure(state="normal" if self.arquivo_csv else "disabled")
    
    def iniciar_processamento(self):
        """Iniciar processamento em thread"""
        if not self.arquivo_csv:
            messagebox.showwarning("Aviso", "Por favor, selecione um arquivo CSV primeiro")
            return
        
        # Limpar logs
        #self.log_text.delete("1.0", "end")
        
        # Resetar status
        for card in [self.card_correios, self.card_loggi, self.card_jt]:
            self.atualizar_status_card(card, "aguardando")
        
        self.progress_bar.set(0)
        
        # Iniciar thread
        thread = threading.Thread(target=self.processar, daemon=True)
        thread.start()
    
    def abrir_html(self):
        """Abrir HTML no navegador"""
        if os.path.exists(self.html_path):
            webbrowser.open(f"file://{os.path.abspath(self.html_path)}")
            self.adicionar_log("Abrindo HTML no navegador...", "info")
        else:
            messagebox.showerror("Erro", f"Arquivo HTML não encontrado:\n{self.html_path}")

if __name__ == "__main__":
    app = FreteComparadorModerno()
    app.mainloop()
