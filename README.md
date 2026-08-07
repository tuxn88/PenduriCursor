# PenduriCursor 🪀

Um overlay transparente e leve para Windows que adiciona penduricalhos animado com simulação física, rastro e partículas ao seu cursor. 

---

## 💾 Download Rápido
Se não quiser instalar o Python, baixa a versão pronta em `.exe` na aba [Releases](../../releases)!
Se quiser que o Icone da barra de tarefas seja o mesmo, salva o .exe em uma pasta junto com o .ico que tem ai no post (emoji de joinha).

## 🚀 Funcionalidades

* **Física Dinâmica:** Movimentação natural com gravidade, mola, rigidez e rotação baseada no movimento do mouse.
* **100% Transparente no Monitor:** Não atrapalha sua jogabilidade ou uso do sistema (Mentirada essa parte aqui, se vc deixar a corda muito pequena ou as particulas muito volumosas vai atrapalhar seu clique).
* **Customizável:** Suporte a GIFs/PNGs animados (estados parado e em movimento), customização de corda, rastro de linha e emissor de partículas.
* **Gerenciador de Presets:** Salve e carregue suas configurações preferidas facilmente.
* **Modo Bandeja (Tray):** Roda em segundo plano na barra de tarefas.

---

## 🛠️ Como Executar

### Pré-requisitos
Certifique-se de ter o **Python 3.10+** instalado em sua máquina.

### Instalação das Dependências PARA EXECUTAR COM PYTHON
Abra o terminal na pasta do projeto e instale as bibliotecas necessárias:

```bash
pip install customtkinter pynput pillow pystray
