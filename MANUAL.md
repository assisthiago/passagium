# Manual de Utilização — Sistema de Passagem de Plantão

Este manual descreve **como usar** o sistema de passagem de plantão no **Django Admin (Unfold)**, incluindo **regras de negócio**, **configurações**, e **cenários operacionais**.

> Importante: este MVP foi desenhado para uso **100% dentro do Admin**, evitando telas customizadas.

---

## 1) Conceitos principais

### Empresa (Company)

Representa o “cliente” (tenant). Tudo no sistema é vinculado a uma empresa.

- Ao criar uma empresa, o sistema cria automaticamente a **Configuração da Empresa (CompanySettings)**.
- A empresa pode ser marcada como ativa/inativa.

### Configuração da Empresa (CompanySettings)

Define políticas e comportamentos para a empresa.

Principais opções:

- **Escopo padrão**: Global ou Site/Unidade
- **Exige destinatários**: se ativado, não permite “Entregar” sem destinatários
- **Fechamento exige todos os recibos**: se ativado, não permite “Fechar” enquanto recibos obrigatórios estiverem pendentes
- **Política de recibo**: “Apenas confirmação” ou “Assinatura obrigatória” (assinatura é futura; no MVP usamos confirmação)
- **Permitir itens sem categoria**: se desativado, o operador deve usar categorias (recomendado)

### Unidade (Site)

Um local onde o plantão acontece (ex.: portaria, hospital X, posto Y, base Z).

### Turno (Shift)

Um turno de trabalho (ex.: manhã, tarde, noite). Pode ter horário início/fim.

### Equipe (Team)

Um agrupamento organizacional (ex.: Equipe A, Plantão Noturno, Time de Ronda).

### Membro da Equipe (TeamMember)

Vincula usuário a uma equipe. Permite selecionar destinatários por equipe e o sistema expande para usuários reais.

### Categoria de Item (ItemCategory) e Tag (Tag)

- Categoria: “tipo” principal do item (ex.: Ocorrência, Pendência, Aviso, Rotina)
- Tag: marcação para facilitar busca/filtro (ex.: “portão”, “ambulância”, “viatura”, “sala 3”)

### Passagem de Plantão (Handover)

Documento do plantão com contexto (empresa, unidade, turno, período), conteúdo e destinatários.

Estados do Handover:

- **Rascunho**: em edição
- **Entregue**: plantão foi entregue (cria recibos para destinatários)
- **Recebido/Confirmado (ACKED)**: há confirmação (ou todas, dependendo da policy)
- **Fechado**: plantão encerrado

### Itens da Passagem (HandoverItem)

Entradas estruturadas dentro do handover: ocorrências, pendências, avisos etc.

### Recibo do destinatário (HandoverRecipient)

Registro de confirmação individual por usuário (data/hora de confirmação e tipo).

### Soft Delete (Exclusão lógica)

Quando um registro é “excluído”, ele não desaparece do banco:

- fica marcado como **excluído** e com data **excluído em**
- pode ser restaurado no Admin (action “Restaurar selecionados”)

---

## 2) Regras de negócio e integridade

### 2.1 Regras de empresa (Company-safe)

O sistema impede/ajusta automaticamente combinações inválidas entre empresas:

- Uma **unidade** deve pertencer à mesma empresa do handover
- Um **turno** deve pertencer à mesma empresa do handover
- Uma **categoria** deve pertencer à mesma empresa do handover
- **Tags** devem pertencer à mesma empresa do item/handover
- **Equipes** destinatárias devem pertencer à mesma empresa do handover

Se o operador selecionar itens de outra empresa, o sistema:

- bloqueia ações críticas (ex.: Entregar)
- ou remove automaticamente vínculos inválidos (ex.: tags/equipes) e avisa no Admin

### 2.2 Escopo do plantão: Global x Unidade

- **Escopo = Site/Unidade**: campo “Unidade” é obrigatório
- **Escopo = Global**: campo “Unidade” deve ficar vazio

### 2.3 Fluxo travado por ações (evita erro operacional)

Após a passagem sair de **Rascunho**, o sistema bloqueia alterações de campos operacionais (ex.: escopo/unidade/turno/destinatários/período).

O status não deve ser “editado na mão”; a mudança ocorre via ações do Admin:

- Entregar
- Confirmar recebimentos
- Fechar

### 2.4 Regras de entrega

Ao executar “Entregar”:

- o sistema exige ao menos 1 item na passagem
- se a configuração “Exige destinatários” estiver ativa, exige destinatários
- o sistema cria **recibos individuais** para cada destinatário (usuários diretos e membros de equipes)

### 2.5 Regras de confirmação e ACKED

Ao confirmar recibos:

- o sistema registra `confirmado em` no recibo
- o handover pode mudar para **Recebido/Confirmado (ACKED)** conforme a política:
  - se “Fechamento exige todos os recibos” estiver ativo: ACKED ocorre quando todos os recibos obrigatórios forem confirmados
  - caso contrário: ACKED ocorre quando ao menos 1 recibo for confirmado

### 2.6 Regras de fechamento

Ao “Fechar”:

- só é permitido se o handover estiver **Entregue** ou **ACKED**
- se “Fechamento exige todos os recibos” estiver ativo, bloqueia fechamento enquanto houver recibos obrigatórios pendentes

---

## 3) Operação passo a passo (cenários)

### Cenário A — Criar empresa e preparar ambiente

1. Acesse o Admin
2. Crie uma **Empresa**
   - O sistema cria automaticamente a **Configuração da empresa**
3. Crie **Unidades**
4. Crie **Turnos**
5. Crie **Equipes**
6. Crie **Membros da equipe** (vincule usuários às equipes)
7. Crie **Categorias de item**
8. Crie **Tags**

Recomendação:

- Tenha ao menos 1 unidade, 1 turno, 1 equipe, 1 categoria para padronização.

---

### Cenário B — Passagem por Unidade (Site/Unidade)

Objetivo: plantão por local.

1. Crie uma **Passagem de plantão**:
   - Empresa: selecione a empresa
   - Escopo: Site/Unidade
   - Unidade: selecione a unidade
   - Turno: selecione o turno
   - Início/Fim: configure
   - Assunto/Observações
2. Em “Destinatários”, selecione:
   - usuários e/ou equipes
3. Adicione **Itens** (mínimo 1)
4. (Opcional) adicione **Anexos**
5. Na lista de passagens, selecione e execute:
   - **Entregar passagens selecionadas**

Resultado:

- status vira **Entregue**
- recibos individuais são criados para cada destinatário

---

### Cenário C — Passagem Global (sem unidade)

Objetivo: plantão geral.

1. Crie a passagem:
   - Escopo: Global
   - Unidade: deixar vazio
2. Destinatários/itens/anexos
3. Entregar

---

### Cenário D — Destinatários por Equipe

1. Cadastre a equipe e seus membros (TeamMember)
2. No Handover, selecione a equipe em “Destinatários (equipes)”
3. Entregar

Resultado:

- o sistema gera recibos para cada usuário membro da equipe (expansão automática)

---

### Cenário E — Confirmar recebimento (por recibos)

Existem duas formas:

1. Confirmar selecionando recibos (HandoverRecipient)

- Vá em “Recibos dos destinatários”
- Selecione um ou mais
- Action: **Confirmar recebimento (selecionados)**

2. Confirmar todos os pendentes por passagem

- Vá na lista de Handovers
- Action: **Confirmar recebimentos pendentes (todas as pessoas)**

---

### Cenário F — Fechar plantão

- Vá na lista de Handovers
- Selecione
- Action: **Fechar passagens selecionadas**

Se a configuração exigir todos os recibos, o sistema bloqueará o fechamento até completar as confirmações obrigatórias.

---

## 4) Anexos (evidências)

- Anexos podem ser vinculados diretamente ao Handover e, opcionalmente, a um Item específico.
- Em ambiente de desenvolvimento, o sistema serve mídia se configurado.
- Em produção, normalmente recomenda-se storage (S3), mas isso pode ser uma fase posterior.

---

## 5) Exclusão (soft delete) e restauração

- Em qualquer lista do Admin, é possível excluir (soft delete).
- Para restaurar:
  - selecione registros marcados como excluídos
  - action: **Restaurar selecionados (soft delete)**

---

## 6) Boas práticas operacionais

- Padronize categorias e tags por empresa.
- Use equipes para reduzir erro na seleção de destinatários.
- Não altere dados de contexto depois de entregar (o sistema bloqueia para segurança).
- Use “Fechamento exige todos os recibos” quando for necessário processo formal.

---

## 7) Perguntas frequentes

### “Posso ter vários turnos?”

Sim. Turnos são configuráveis por empresa.

### “Posso operar global ou por unidade?”

Sim. Cada handover define o escopo (Global ou Unidade).

### “O sistema suporta assinatura real?”

No MVP, o recibo é confirmação (flag + data). Assinatura pode ser fase futura.

### “O que acontece se eu tentar usar categoria/tag/equipe de outra empresa?”

O sistema bloqueia ações críticas e/ou remove vínculos inválidos e avisa no Admin.

---
